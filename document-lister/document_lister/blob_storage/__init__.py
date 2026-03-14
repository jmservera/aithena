class BlobStorage:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("Azure Blob Storage support has been removed; document-lister only supports local files.")
