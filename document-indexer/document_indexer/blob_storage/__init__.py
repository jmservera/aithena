import io
import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobServiceClient,
    BlobClient,
    ContainerClient,
    BlobProperties,
)
from azure.core.paging import ItemPaged


class BlobStorage:
    blob_service_client: BlobServiceClient = None

    def __init__(self, account_name: str):
        account_url = f"https://{account_name}.blob.core.windows.net"
        credential = DefaultAzureCredential()
        self.blob_service_client = BlobServiceClient(account_url, credential=credential)

    def list_blobs_flat(self, container_name: str) -> ItemPaged[BlobProperties]:
        container_client = self.blob_service_client.get_container_client(
            container=container_name
        )

        return container_client.list_blobs()

    def download_blob_to_stream(self, container_name:str, file_name:str) -> io.BytesIO:
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, blob=file_name
        )

        # readinto() downloads the blob contents to a stream and returns the number of bytes read
        stream = io.BytesIO()
        num_bytes = blob_client.download_blob().readinto(stream)
        print(f"Downloaded blob {blob_client.blob_name} of length {num_bytes}")
        return stream

    def download_blob_to_file(self, container_name: str):
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, blob="sample-blob.txt"
        )
        with open(file=os.path.join(r"filepath", "filename"), mode="wb") as sample_blob:
            download_stream = blob_client.download_blob()
            sample_blob.write(download_stream.readall())
