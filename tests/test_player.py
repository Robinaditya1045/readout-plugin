#!/usr/bin/env python3
"""
Player tests: audio is streamed into a stand-in player command that writes to a file,
so nothing is ever played out loud.
"""

import shlex
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import player


class TestStreamingPlayer(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "played.mp3"
        self._saved = (dict(player.STREAM_COMMANDS), player.find_audio_player, player.stream_edge_tts, player.stream_gtts)
        player.STREAM_COMMANDS["ffplay"] = ["sh", "-c", f"cat > {shlex.quote(str(self.out))}"]
        player.find_audio_player = lambda: "ffplay"

    def tearDown(self):
        commands, player.find_audio_player, player.stream_edge_tts, player.stream_gtts = self._saved
        player.STREAM_COMMANDS.clear()
        player.STREAM_COMMANDS.update(commands)
        self._tmp.cleanup()

    def test_pipe_starts_the_player_on_the_first_chunk(self):
        pipe = player.PlayerPipe("ffplay")
        self.assertFalse(pipe.started)
        pipe.write(b"chunk-1 ")
        self.assertTrue(pipe.started)
        pipe.write(b"chunk-2")
        pipe.finish()
        self.assertEqual(self.out.read_bytes(), b"chunk-1 chunk-2")

    def test_edge_tts_audio_is_streamed(self):
        async def fake_edge(text, voice, rate, pipe):
            for part in (b"a", b"b", b"c"):
                pipe.write(part)

        player.stream_edge_tts = fake_edge
        self.assertTrue(player.speak("hello", "ava", "+0%"))
        self.assertEqual(self.out.read_bytes(), b"abc")

    def test_falls_back_to_gtts_only_when_edge_produced_nothing(self):
        async def failing_edge(text, voice, rate, pipe):
            raise ConnectionError("offline")

        player.stream_edge_tts = failing_edge
        player.stream_gtts = lambda text, pipe: pipe.write(b"gtts")
        self.assertTrue(player.speak("hello", "ava", "+0%"))
        self.assertEqual(self.out.read_bytes(), b"gtts")

    def test_partial_edge_audio_is_not_repeated_with_gtts(self):
        async def dropping_edge(text, voice, rate, pipe):
            pipe.write(b"first half")
            raise ConnectionError("dropped")

        gtts_calls = []
        player.stream_edge_tts = dropping_edge
        player.stream_gtts = lambda text, pipe: gtts_calls.append(text)
        self.assertTrue(player.speak("hello", "ava", "+0%"))
        self.assertEqual(gtts_calls, [])

    def test_reports_failure_so_system_tts_can_take_over(self):
        async def failing_edge(text, voice, rate, pipe):
            raise ConnectionError("offline")

        def failing_gtts(text, pipe):
            raise ConnectionError("offline")

        player.stream_edge_tts = failing_edge
        player.stream_gtts = failing_gtts
        self.assertFalse(player.speak("hello", "ava", "+0%"))

    def test_google_voice_skips_edge_tts(self):
        async def edge_should_not_run(text, voice, rate, pipe):
            raise AssertionError("edge-tts used for the google voice")

        player.stream_edge_tts = edge_should_not_run
        player.stream_gtts = lambda text, pipe: pipe.write(b"g")
        self.assertTrue(player.speak("hello", "google", "+0%"))


if __name__ == "__main__":
    unittest.main()
