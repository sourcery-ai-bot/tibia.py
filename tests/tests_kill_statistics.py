import unittest

from tests.tests_tibiapy import TestCommons
from tibiapy import KillStatistics, InvalidContent

FILE_KILL_STATISTICS_FULL = "kill_statistics/tibiacom_full.txt"
FILE_KILL_STATISTICS_EMPTY = "kill_statistics/tibiacom_empty.txt"


class TestHighscores(TestCommons, unittest.TestCase):
    # region Tibia.com Tests
    def testKillStatistics(self):
        content = self._load_resource(FILE_KILL_STATISTICS_FULL)
        kill_statistics = KillStatistics.from_content(content)

        self.assertEqual(kill_statistics.world, "Gladera")
        self.assertEqual(len(kill_statistics.entries), 920)
        self.assertIsNotNone(kill_statistics.total)
        self.assertIsNotNone(kill_statistics.url)

        # players shortcurt property
        self.assertEqual(kill_statistics.players, kill_statistics.entries["players"])
        self.assertEqual(kill_statistics.players.last_day_killed, 2)
        self.assertEqual(kill_statistics.players.last_day_killed, kill_statistics.players.last_day_players_killed)
        self.assertEqual(kill_statistics.players.last_week_killed, 7)
        self.assertEqual(kill_statistics.players.last_week_killed, kill_statistics.players.last_week_players_killed)

    def testKillStatisticsEmpty(self):
        content = self._load_resource(FILE_KILL_STATISTICS_EMPTY)
        kill_statistics = KillStatistics.from_content(content)

        self.assertIsNone(kill_statistics)

    def testKillStatisticsUnrelated(self):
        content = self._load_resource(self.FILE_UNRELATED_SECTION)
        with self.assertRaises(InvalidContent):
            kill_statistics = KillStatistics.from_content(content)

    # endregion
