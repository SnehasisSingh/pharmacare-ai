
import logging
from getpass import getpass
from pathlib import Path

from qdrant_client import QdrantClient, models


PROJECT_ROOT = Path(__file__).resolve().parents[1]

LOCAL_QDRANT_PATH = PROJECT_ROOT / "data" / "qdrant_storage"

COLLECTION_NAME = "medical_knowledge"

QDRANT_URL = (
    "https://5c4b8d6c-900a-47a8-a5b7-77fc02364f1a."
    "us-east-1-1.aws.cloud.qdrant.io"
)

BATCH_SIZE = 50

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def migrate_collection():

    if not LOCAL_QDRANT_PATH.exists():
        raise FileNotFoundError(
            f"Local Qdrant database not found: {LOCAL_QDRANT_PATH}"
        )

    api_key = getpass("Enter your Qdrant Cloud API key: ")

    if not api_key.strip():
        raise ValueError("Qdrant API key cannot be empty.")

    source_client = QdrantClient(
        path=str(LOCAL_QDRANT_PATH)
    )

    cloud_client = QdrantClient(
        url=QDRANT_URL,
        api_key=api_key,
        timeout=60,
    )

    try:
        # Verify source collection.
        if not source_client.collection_exists(COLLECTION_NAME):
            raise ValueError(
                f"Local collection not found: {COLLECTION_NAME}"
            )

        source_info = source_client.get_collection(
            COLLECTION_NAME
        )

        source_count = source_client.count(
            collection_name=COLLECTION_NAME,
            exact=True,
        ).count

        logger.info("Local collection: %s", COLLECTION_NAME)
        logger.info("Local point count: %d", source_count)

        # Never overwrite an existing cloud collection automatically.
        if cloud_client.n(COLLECTION_NAME):
            raise ValueError(
                f"Cloud collection '{COLLECTION_NAME}' already exists. "
                "Migration stopped to protect existing data."
            )

        # Preserve the existing vector configuration.
        vectors_config = source_info.config.params.vectors

        cloud_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=vectors_config,
        )

        logger.info("Cloud collection created successfully.")

        offset = None
        migrated_count = 0

        while True:

            points, next_offset = source_client.scroll(
                collection_name=COLLECTION_NAME,
                limit=BATCH_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )

            if not points:
                break

            cloud_points = [
                models.PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=point.payload,
                )
                for point in points
            ]

            cloud_client.upsert(
                collection_name=COLLECTION_NAME,
                points=cloud_points,
                wait=True,
            )

            migrated_count += len(cloud_points)

            logger.info(
                "Migrated %d / %d points",
                migrated_count,
                source_count,
            )

            if next_offset is None:
                break

            offset = next_offset

        # Verify destination collection.
        cloud_count = cloud_client.count(
            collection_name=COLLECTION_NAME,
            exact=True,
        ).count

        logger.info("Migration completed.")
        logger.info("Local points: %d", source_count)
        logger.info("Cloud points: %d", cloud_count)

        if source_count != cloud_count:
            raise RuntimeError(
                "Migration verification failed. "
                f"Local: {source_count}, Cloud: {cloud_count}"
            )

        logger.info(
            "SUCCESS: All %d points migrated to Qdrant Cloud.",
            cloud_count,
        )

    finally:
        source_client.close()
        cloud_client.close()


if __name__ == "__main__":
    migrate_collection()
