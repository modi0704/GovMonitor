"""Extension points (MASTERPLAN 6.6). Version 1 has no virus scanner; this hook is where one goes."""


class UploadRejected(Exception):
    pass


def scan_upload(file) -> None:
    """Called for every uploaded file before it is stored. Raise UploadRejected to refuse it.

    No-op in version 1 (virus scanning is out of scope, 1.3). A deployment can replace this
    function, e.g. to send the stream to ClamAV, without touching the upload code.
    """
    return None
