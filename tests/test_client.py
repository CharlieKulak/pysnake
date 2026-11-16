"""Tests of PySnake itself (drawing, the online client, world records).

The game rules and the server are tested in the OpenSnake server's repository.
"""

import json
import os
import random
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from opensnake import cosmetics as cos  # noqa: E402
from opensnake.game import Apple, Game, Seg, game_to_state  # noqa: E402
from opensnake.speedrun import CATEGORIES, Run  # noqa: E402

from pysnake.records import Records  # noqa: E402



class SkinDrawTests(unittest.TestCase):
    def test_every_skin_draws_on_a_moving_snake(self):
        """Regression: gradient skins made an invalid colour for the cell the tail slides out of,
        which crashed the game as soon as the snake moved (it froze in the browser)."""
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        pygame.display.set_mode((10, 10))
        from pysnake.render import Renderer, View
        r = Renderer()
        for skin in cos.SKINS:
            g = Game(10, 9, (), 1, rng=random.Random(1))
            g.started = True
            for _ in range(3):
                g.step()
                for t in (0.0, 0.5, 0.99):
                    r.draw_board(g, t, 1000.0, ((61, 111, 232), (122, 162, 255)),
                                 View(32, 0, 0, 320, 288, 10, 9), skin=skin)
            for i in range(14):  # past the end of the body too
                c = cos.skin_color(skin, i, 4, 777.0)
                self.assertTrue(all(0 <= v <= 255 for v in c), (skin.id, i, c))


class ClientRobustnessTests(unittest.TestCase):
    """The game side: a bad reply can't freeze the game, and downloaded pictures decode."""

    def setUp(self):
        import os
        import tempfile
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        self.cfg = tempfile.TemporaryDirectory()
        os.environ["PYSNAKE_CONFIG_DIR"] = self.cfg.name
        from pysnake.app import App
        self.app = App()

    def tearDown(self):
        self.cfg.cleanup()

    def test_a_failing_reply_handler_does_not_stop_the_game(self):
        class Done:
            done = ok = True
            def poll(self):
                return True
        later = []
        on = self.app.online
        on.requests = [(Done(), lambda r: 1 / 0), (Done(), lambda r: later.append("ran"))]
        on.poll()  # used to raise, which stopped the main loop in the browser
        self.assertEqual(later, ["ran"])
        self.assertIn("went wrong", on.message)

    def test_pictures_decode(self):
        import base64
        from pysnake.net import decode_png, load_picture
        img = decode_png(base64.b64decode(load_picture("packaging/linux/pysnake-256.png")))
        self.assertEqual(img.get_size(), (128, 128))


class PathTests(unittest.TestCase):
    def test_head_moves_without_jumps_through_turns(self):
        import math
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        from pysnake.render import build_snake_path
        g = Game(17, 15, (), 1, rng=random.Random(1))
        g.apples.clear()
        g.started = True
        g.step()  # get moving first: before the first step there is nothing to interpolate
        heads = []
        g.input("down")
        g.input("left")
        for _ in range(4):
            for t in (0.0, 0.25, 0.5, 0.75):
                if t >= 0.5:
                    g.plan()
                path, s_head, _ = build_snake_path(g, g.snakes[0], g.prev[0], t)
                heads.append(path.point(s_head)[:2])
            g.step()
        steps = [math.dist(a, b) for a, b in zip(heads, heads[1:])]
        self.assertLess(max(steps), 0.26)
        self.assertGreater(min(steps), 0.18)


class PredictionTests(unittest.TestCase):
    """The joining player's own snake reacts to their keys at once (client-side prediction)."""

    def setUp(self):
        import os
        import tempfile
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["PYSNAKE_CONFIG_DIR"] = self.tmp.name
        from pysnake.app import App
        self.app = App()
        self.on = self.app.online
        self.server = Game(20, 16, (), 1, rng=random.Random(1), teams=[0, 1])  # stands in for the server
        self.sent = []

        class FakeSocket:
            state = "open"
            inbox = []
            def send(_, m): self.sent.append(m)
            def poll(_):
                out, FakeSocket.inbox = FakeSocket.inbox, []
                return out
        self.sock = FakeSocket
        self.on.sock = FakeSocket()
        self.on.my_id = 1
        self.on.on_message({"t": "start", "you": 1, "tick_ms": 130, "state": game_to_state(self.server)})
        self.on.ping_ms = 20  # a quick connection: turns early in a cell make that cell

    def tearDown(self):
        self.tmp.cleanup()

    def server_step(self):
        for m in self.sent:
            if m["t"] == "input":
                self.server.input_for(1, m["d"])
        self.sent.clear()
        self.server.started = True
        self.server.step()
        return {"t": "state", "s": game_to_state(self.server)}

    def test_turn_shows_immediately_then_server_confirms(self):
        me = lambda: self.on.game.snakes[1]
        self.assertEqual(me().dir, "left")
        self.on.turn("up")
        self.assertEqual(self.sent, [{"t": "input", "d": "up", "step": 1}])  # sent, with the move it's for
        self.assertEqual(me().planned, "up")                       # ...but shown right away
        self.on.on_message(self.server_step())                     # server applies it
        self.assertEqual(me().dir, "up")
        self.assertEqual(self.on.pending, [])

    def test_a_turn_too_late_for_this_cell_waits_for_the_next(self):
        me = lambda: self.on.game.snakes[1]
        self.app.acc = 120  # the head is nearly through its cell: the turn can't reach the server in time
        self.on.turn("down")
        self.assertEqual(self.sent, [{"t": "input", "d": "down", "step": 2}])
        self.assertIsNone(me().planned)  # not shown here: it won't happen here
        self.sent.clear()                # (the server holds it for move 2)
        self.server.started = True
        self.server.step()
        self.app.acc = 0
        self.on.on_message({"t": "state", "s": game_to_state(self.server)})
        self.assertEqual(me().planned, "down")  # now it's this cell: shown at once

    def test_turns_aim_further_ahead_on_a_slow_connection(self):
        self.app.acc = 0
        for ping, ahead in ((20, 1), (100, 1), (115, 2), (250, 3)):
            self.on.ping_ms = ping
            self.assertEqual(self.on.moves_ahead(), ahead, ping)

    def test_unapplied_turn_is_dropped_eventually(self):
        import pygame
        self.on.turn("up")
        self.sent.clear()
        self.on.pending = [("up", pygame.time.get_ticks() - 10_000, 5)]  # sent long ago, never applied
        self.server.started = True
        self.server.step()
        self.on.on_message({"t": "state", "s": game_to_state(self.server)})
        self.assertEqual(self.on.pending, [])
        self.assertIsNone(self.on.game.snakes[1].planned)

    def test_reverse_is_not_predicted(self):
        self.on.turn("right")  # straight back into yourself: the server ignores it, so do we
        self.assertEqual(self.sent, [])
        self.assertEqual(self.on.pending, [])

    def test_backlog_draws_only_the_newest_state(self):
        self.server.started = True
        h = self.server.snakes[1].head
        self.server.apples.append(Apple(h.x - 1, h.y, "apple", 99))
        msgs = [self.server_step() for _ in range(3)]  # first one has an "eat" event
        self.assertTrue(any(e[0] == "eat" for e in msgs[0]["s"]["events"]))
        applied = []
        real = self.on.on_message
        self.on.on_message = lambda m: (applied.append(m["t"]), real(m))
        self.sock.inbox = msgs
        played = []
        self.app.sfx.play = played.append
        self.on.poll()
        self.assertEqual(applied, ["state"])                      # one state drawn, not three
        self.assertEqual(self.on.game.tick, self.server.tick)     # the newest one
        self.assertIn("eat", played)                              # the skipped one's sound still plays


class RecordsTests(unittest.TestCase):
    def test_bundled_and_newer_cache(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "records.json"
            cache.write_text(json.dumps({"updated": "2999-01-01", "records": {
                "sprint10": {"time_ms": 9000, "player": "someone"},
                "not_a_category": {"time_ms": 1},
                "sprint25": {"time_ms": "fast"}}}))
            r = Records(cache)
            self.assertEqual(r.get("sprint10")["time_ms"], 9000)
            self.assertIsNone(r.get("not_a_category"))
            self.assertIsNone(r.get("sprint25"))

    def test_older_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "records.json"
            cache.write_text(json.dumps({"updated": "2000-01-01", "records": {"sprint10": {"time_ms": 1}}}))
            r = Records(cache)
            self.assertEqual(r.source, "bundled")


class CustomRecordsTests(unittest.TestCase):
    def test_custom_world_records_are_accepted(self):
        from opensnake.speedrun import make_custom
        cid = make_custom(10, 9, [], 5, 1, 130).id
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "records.json"
            cache.write_text(json.dumps({"updated": "2999-01-01",
                                         "records": {cid: {"time_ms": 4000, "player": "x"}}}))
            self.assertEqual(Records(cache).get(cid)["time_ms"], 4000)


class SiteRecordsTests(unittest.TestCase):
    def test_site_records_replace_and_restore(self):
        r = Records(None)
        offline = dict(r.records)
        r.set_server({"sprint10": {"time_ms": 5000, "player": "site-hero"}, "junk": "x"}, "snake.example.com")
        self.assertEqual(r.get("sprint10")["player"], "site-hero")
        self.assertIsNone(r.get("junk"))
        self.assertEqual(r.source, "site:snake.example.com")
        r.set_server({}, "other.example.com")  # switching sites keeps the original to restore
        self.assertIsNone(r.get("sprint10"))
        r.clear_server()
        self.assertEqual(r.records, offline)
        self.assertNotEqual(r.source.split(":")[0], "site")


if __name__ == "__main__":
    unittest.main()
