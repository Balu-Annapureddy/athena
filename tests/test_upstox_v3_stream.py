"""Offline unit tests for SDK streaming lifecycle; no credentials or network."""
import unittest
from core.data.connectors.upstox_v3_stream import LiveFeed


class FakeStream:
    def __init__(self, client):
        self.handlers = {}
        self.subscriptions = []
        self.reconnect = None
        self.disconnected = False

    def on(self, event, cb):
        self.handlers[event] = cb

    def auto_reconnect(self, *args):
        self.reconnect = args

    def connect(self):
        self.handlers["open"]()

    def subscribe(self, keys, mode):
        self.subscriptions.append((keys, mode))

    def disconnect(self):
        self.disconnected = True


class FakeSDK:
    last = None

    class Configuration:
        access_token = None

    class ApiClient:
        def __init__(self, configuration):
            self.configuration = configuration

    @staticmethod
    def MarketDataStreamerV3(client):
        FakeSDK.last = FakeStream(client)
        return FakeSDK.last


class StreamTests(unittest.TestCase):
    def test_connect_subscribe_and_reconnect(self):
        events = []
        feed = LiveFeed(["NSE_EQ|INE002A01018"], events.append, access_token="fake-token", sdk=FakeSDK)
        feed.start()
        stream = FakeSDK.last
        self.assertTrue(feed.connected)
        self.assertEqual(stream.reconnect, (True, 10, 5))
        self.assertEqual(stream.subscriptions, [(["NSE_EQ|INE002A01018"], "full")])
        self.assertFalse(feed.is_fresh)
        stream.handlers["message"]({"test": True})
        self.assertTrue(feed.is_fresh)
        self.assertEqual(len(events), 1)
        stream.handlers["reconnecting"]()
        self.assertFalse(feed.connected)
        stream.handlers["open"]()
        self.assertEqual(len(stream.subscriptions), 2)
        feed.stop()
        self.assertTrue(stream.disconnected)
        self.assertFalse(feed.is_fresh)

    def test_rejects_missing_instrument(self):
        with self.assertRaises(ValueError):
            LiveFeed(["RELIANCE"], lambda x: None, access_token="fake", sdk=FakeSDK)

    def test_prevents_duplicate_start(self):
        feed = LiveFeed(["NSE_EQ|X"], lambda x: None, access_token="fake", sdk=FakeSDK)
        feed.start()
        with self.assertRaises(RuntimeError):
            feed.start()
        feed.stop()


if __name__ == "__main__":
    unittest.main()
