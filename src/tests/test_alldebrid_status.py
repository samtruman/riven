from program.services.downloaders.alldebrid import AllDebridDownloader


def test_status_uses_matching_magnet_from_array(monkeypatch):
    downloader = object.__new__(AllDebridDownloader)
    downloader.initialized = True

    class Handler:
        def execute(self, *_args, **_kwargs):
            return {"magnets": [{"id": 1, "filename": "wrong", "status": "Ready", "size": 1, "downloaded": 1, "uploadDate": 1}, {"id": 2, "filename": "right", "status": "Ready", "size": 2, "downloaded": 2, "uploadDate": 2}]}

    downloader.api = type("Api", (), {"status_request_handler": Handler()})()
    info = downloader.get_torrent_info("2")
    assert info.id == 2
    assert info.name == "right"


def test_status_uses_matching_magnet_from_id_mapping(monkeypatch):
    downloader = object.__new__(AllDebridDownloader)
    downloader.initialized = True

    class Handler:
        def execute(self, *_args, **_kwargs):
            return {"magnets": {"2": {"filename": "right", "status": "Ready", "size": 2, "downloaded": 2, "uploadDate": 2}}}

    downloader.api = type("Api", (), {"status_request_handler": Handler()})()
    info = downloader.get_torrent_info("2")
    assert str(info.id) == "2"
    assert info.name == "right"


def test_status_uses_unwrapped_single_magnet(monkeypatch):
    downloader = object.__new__(AllDebridDownloader)
    downloader.initialized = True

    class Handler:
        def execute(self, *_args, **_kwargs):
            return {"magnets": {"id": 2, "filename": "right", "status": "Ready", "size": 2, "uploadDate": 2}}

    downloader.api = type("Api", (), {"status_request_handler": Handler()})()
    info = downloader.get_torrent_info("2")
    assert info.id == 2
    assert info.name == "right"
    assert info.progress == 1
