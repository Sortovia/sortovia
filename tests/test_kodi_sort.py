import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kodi_sort as ks  # noqa: E402

D = Path("/dest")


def rel(name):
    target, kind, note = ks.target_for(name, D)
    return (str(target.relative_to(D)) if target else None), kind, note


class TV(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(rel("Show.Name.S01E02.mkv")[0],
                         "TV/Show Name/Season 01/Show Name S01E02.mkv")

    def test_resolution_not_read_as_episode(self):
        # bug: used to give S01E02E108 / S01E02E720
        self.assertEqual(rel("Show.Name.S01E02.1080p.WEB.mkv")[0],
                         "TV/Show Name/Season 01/Show Name S01E02.mkv")
        self.assertEqual(rel("Show S01E02 720p.mkv")[0],
                         "TV/Show/Season 01/Show S01E02.mkv")

    def test_multi_episode(self):
        for n in ("Show.Name.S01E01E02.mkv", "Show.Name.S01E01-E02.mkv"):
            self.assertEqual(rel(n)[0], "TV/Show Name/Season 01/Show Name S01E01E02.mkv", n)

    def test_x_style(self):
        self.assertEqual(rel("show.name.1x05.mkv")[0],
                         "TV/Show Name/Season 01/Show Name S01E05.mkv")

    def test_year_in_show(self):
        self.assertEqual(rel("Show.Name.2019.S02E10.mkv")[0],
                         "TV/Show Name (2019)/Season 02/Show Name (2019) S02E10.mkv")

    def test_real_download_name(self):
        self.assertEqual(
            rel("The.Silver.Harbor.Ember.Coast.S02E01.1080p.x265-BETA.mkv")[0],
            "TV/The Silver Harbor Ember Coast/Season 02/The Silver Harbor Ember Coast S02E01.mkv")

    def test_anime_absolute(self):
        target, kind, note = rel("[SubTeam] Ironclad Ultimate - 03 (1080p).mkv")
        self.assertEqual(target, "TV/Ironclad Ultimate/Season 01/Ironclad Ultimate S01E03.mkv")
        self.assertIn("absolute", note)

    def test_sxxeyy_not_flagged_absolute(self):
        self.assertEqual(rel("Show.S01E02.mkv")[2], "")


class Anime(unittest.TestCase):
    """Real names that the Xbox add-on v1.2.1 skipped as 'can't tell TV vs movie'."""

    def test_underscores_and_paren_group(self):
        self.assertEqual(
            rel("(Group_One)_Tinman_Meadow_-_07_(BD_1080p).mkv")[0],
            "TV/Tinman Meadow/Season 01/Tinman Meadow S01E07.mkv")

    def test_dash_stuck_to_word(self):
        self.assertEqual(
            rel("[FanGroup] Paragon -the motto- 05 [1080p] [x265] [qc].mkv")[0],
            "TV/Paragon the Motto/Season 01/Paragon the Motto S01E05.mkv")

    def test_tag_glued_to_name(self):
        self.assertEqual(
            rel("[SubCrew]Tinman_Meadow_-_01_(Dual Audio_10bit_BD1080p_x265).mkv")[0],
            "TV/Tinman Meadow/Season 01/Tinman Meadow S01E01.mkv")

    def test_credits_with_underscores(self):
        self.assertEqual(rel("(Group_One)_Tinman_Meadow_-_NCED_(BD_1080p).mkv")[0],
                         "TV/Tinman Meadow/Season 00/Tinman Meadow S00E01 - NCED.mkv")

    def test_credits_clip_to_specials(self):
        self.assertEqual(
            rel("Tinman%20Meadow%20%28Uncensored%20Textless%20Opening%29%20%20%20%5BOtherSubs%5D.mkv")[0],
            "TV/Tinman Meadow/Season 00/Tinman Meadow S00E01 - Uncensored Textless Opening.mkv")

    def test_sorted_credits_clip_stays(self):
        self.assertEqual(rel("Tinman Meadow S00E02 - Uncensored Textless Opening.mkv")[0],
                         "TV/Tinman Meadow/Season 00/Tinman Meadow S00E02.mkv")

    def test_hyphenated_titles_not_episodes(self):
        self.assertIsNone(rel("Apollo-13.mkv")[0])
        self.assertEqual(rel("Spider-Man.2002.1080p.mkv")[0],
                         "Movies/Spider-Man (2002)/Spider-Man (2002).mkv")


class Specials(unittest.TestCase):
    def test_ova_with_title_goes_to_season_00(self):
        self.assertEqual(
            rel("Tinman Meadow OVA - The Long Road Home  [OtherSubs].mkv")[0],
            "TV/Tinman Meadow/Season 00/Tinman Meadow S00E01 - The Long Road Home.mkv")

    def test_ova_with_number(self):
        self.assertEqual(rel("[SubTeam] Show - OVA2 (1080p).mkv")[0],
                         "TV/Show/Season 00/Show S00E02.mkv")

    def test_ova_group_tags_not_in_title(self):
        self.assertEqual(rel("(Group_One)_Tinman_Meadow_-_OVA_(BD_1080p).mkv")[0],
                         "TV/Tinman Meadow/Season 00/Tinman Meadow S00E01.mkv")

    def test_special_word_in_movie_title(self):
        self.assertEqual(rel("Special.Forces.2011.1080p.mkv")[0],
                         "Movies/Special Forces (2011)/Special Forces (2011).mkv")


class Movies(unittest.TestCase):
    def test_site_prefix_removed(self):
        self.assertEqual(
            rel("www.ExampleSite.org    -    The Nightwarden 2022 1080p REPACK BluRay DDP 5 1 10bit H265-ALPHA.mkv")[0],
            "Movies/The Nightwarden (2022)/The Nightwarden (2022).mkv")

    def test_release_junk(self):
        self.assertEqual(rel("Movie.Name.2019.1080p.BluRay.x264-GRP.mkv")[0],
                         "Movies/Movie Name (2019)/Movie Name (2019).mkv")

    def test_year_in_title(self):
        # bug: used to take 2001 as the year and leave an empty title
        self.assertEqual(rel("2001.A.Space.Odyssey.1968.1080p.mkv")[0],
                         "Movies/2001 a Space Odyssey (1968)/2001 a Space Odyssey (1968).mkv")

    def test_parenthesised_year(self):
        self.assertEqual(rel("Movie Name (2019).mp4")[0],
                         "Movies/Movie Name (2019)/Movie Name (2019).mp4")

    def test_no_year_skipped(self):
        self.assertIsNone(rel("Some.Movie.1080p.mkv")[0])


class Subtitles(unittest.TestCase):
    def test_release_word_not_language(self):
        # bug: WEB was taken as a language tag
        self.assertEqual(rel("Show.S01E01.WEB.srt")[0], "TV/Show/Season 01/Show S01E01.srt")

    def test_language_kept(self):
        self.assertEqual(rel("Show.S01E01.en.srt")[0], "TV/Show/Season 01/Show S01E01.en.srt")
        self.assertEqual(rel("Movie.2019.eng.srt")[0],
                         "Movies/Movie (2019)/Movie (2019).en.srt")


class Skips(unittest.TestCase):
    def test_credits_clip(self):
        self.assertIsNone(rel("NCOP One Reason (Censored) [7A42D245].mkv")[0])

    def test_textless_opening(self):
        # with the show's name in front it goes to Specials (Season 00); without one it's skipped
        self.assertEqual(rel("Tinman Meadow (Uncensored Textless Opening)  [OtherSubs].mkv")[0],
                         "TV/Tinman Meadow/Season 00/Tinman Meadow S00E01 - Uncensored Textless Opening.mkv")
        self.assertIsNone(rel("NCED2.mkv")[0])

    def test_sample(self):
        self.assertIsNone(rel("Movie.2019.sample.mkv")[0])

    def test_comic(self):
        self.assertEqual(rel("Ironclad v01.cbz")[0], "Comics/Ironclad/Ironclad v01.cbz")

    def test_comic_series_folders(self):
        self.assertEqual(rel("Ironclad (2).cbz")[0], "Comics/Ironclad/Ironclad (2).cbz")
        self.assertEqual(rel("Saga 054 (2018) (Digital).cbr")[0], "Comics/Saga/Saga 054 (2018) (Digital).cbr")
        self.assertEqual(rel("Spider-Man 2099 001 (1992).cbz")[0],
                         "Comics/Spider-Man 2099/Spider-Man 2099 001 (1992).cbz")

    def test_pdf_not_a_comic_by_default(self):
        # bills and manuals in a phone's Download folder were sent as comics
        target, kind, _ = ks.target_for("Verizon_bill_December_18_2022.pdf", D, "/storage/emulated/0/Download")
        self.assertIsNone(target)
        self.assertIn("document", kind)

    def test_pdf_in_comics_folder(self):
        target = ks.target_for("Nightwarden 001.pdf", D, "/downloads/Nightwarden Comics")[0]
        self.assertEqual(str(target.relative_to(D)), "Comics/Nightwarden/Nightwarden 001.pdf")
        target = ks.target_for("Berserk v01.epub", D, "/downloads/manga/Berserk")[0]
        self.assertEqual(str(target.relative_to(D)), "Comics/Berserk/Berserk v01.epub")

    def test_hidden_file(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, ".pending-123-Show.S01E01.mkv")
            p.write_bytes(b"x")
            self.assertIsNone(ks.plan_for(p, D)[0])


class SafeNames(unittest.TestCase):
    def test_bad_chars(self):
        self.assertEqual(ks.safe('Star Wars: A New Hope?'), "Star Wars - A New Hope")
        self.assertEqual(ks.safe('A<b>c"d|e*f'), "Abcdef")

    def test_trailing_dot_space(self):
        self.assertEqual(ks.safe("What If... "), "What If")

    def test_used_in_targets(self):
        target = rel("What.If.S01E01.mkv")[0]
        self.assertNotRegex(target, r'[<>:"|?*]')


class AudioTracks(unittest.TestCase):
    def test_episode_tag_without_show_name(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon" / "script.kodisorter"))
        from sortlib import episode_tag, AUDIO
        self.assertIn(".mka", AUDIO)
        self.assertEqual(episode_tag("S01E05 - Quiet Streets.mka"), "S01E05")
        self.assertEqual(episode_tag("Neonpunk Skyrunners - S01E05 - Quiet Streets.mkv"), "S01E05")
        self.assertEqual(episode_tag("[SubTeam] Frieren - 05 (1080p).mka"), "S01E05")
        self.assertIsNone(episode_tag("Movie.2019.English.mka"))


class InPlace(unittest.TestCase):
    """dest on the same drive as src: files are renamed, already-sorted ones ignored."""

    def test_sort_in_place(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            src = root / "Completed"
            src.mkdir()
            ep = src / "Show.Name.S01E02.1080p.mkv"
            with open(ep, "wb") as fh:
                fh.truncate(ks.MIN_VIDEO_BYTES + 1)  # sparse file, no real disk use
            (src / ".pending-1-Other.S01E01.mkv").write_bytes(b"x")
            already = root / "TV" / "Old (2000)" / "Season 01" / "Old (2000) S01E01.mkv"
            already.parent.mkdir(parents=True)
            already.write_bytes(b"x")

            argv = sys.argv
            sys.argv = ["kodi_sort.py", "--src", str(root), "--dest", str(root), "--go"]
            try:
                ks.main()
            finally:
                sys.argv = argv

            self.assertFalse(ep.exists())
            self.assertTrue((root / "TV/Show Name/Season 01/Show Name S01E02.mkv").exists())
            self.assertTrue((src / ".pending-1-Other.S01E01.mkv").exists())
            self.assertTrue(already.exists())

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            ep = root / "Show.S01E02.mkv"
            with open(ep, "wb") as fh:
                fh.truncate(ks.MIN_VIDEO_BYTES + 1)
            before = sorted(os.walk(root))
            argv = sys.argv
            sys.argv = ["kodi_sort.py", "--src", str(root), "--dest", str(root)]
            try:
                ks.main()
            finally:
                sys.argv = argv
            self.assertEqual(before, sorted(os.walk(root)))


class Tutorials(unittest.TestCase):
    def test_named_course_goes_to_program_folder(self):
        self.assertEqual(rel("AutoCAD 2026 FULL Course For BEGINNERS!.mp4")[:2],
                         ("Tutorials/AutoCAD/AutoCAD 2026 FULL Course For BEGINNERS!.mp4", "tutorial"))
        self.assertEqual(rel("Autodesk Revit - Full Beginner Course \uff5c Complete Project - Start to finish.webm")[0],
                         "Tutorials/Revit/Autodesk Revit - Full Beginner Course \uff5c Complete Project - Start to finish.webm")

    def test_dash_number_is_not_an_episode(self):
        self.assertEqual(rel("AutoCAD 3D House Modeling Tutorial - 1.mp4")[0],
                         "Tutorials/AutoCAD/AutoCAD 3D House Modeling Tutorial - 1.mp4")

    def test_users_own_subject_folder_wins(self):
        t, kind, _ = ks.target_for("Walls and Floors.mp4", D, "/x/Download/Tutorials/Revit")
        self.assertEqual((str(t.relative_to(D)), kind), ("Tutorials/Revit/Walls and Floors.mp4", "tutorial"))
        t, _, _ = ks.target_for("Intro.mp4", D, "/x/Tutorials")
        self.assertEqual(str(t.relative_to(D)), "Tutorials/Other/Intro.mp4")

    def test_unknown_program_goes_to_other(self):
        self.assertEqual(rel("Cooking basics full course.mp4")[0], "Tutorials/Other/Cooking basics full course.mp4")

    def test_films_and_episodes_unchanged(self):
        self.assertEqual(rel("How to Train Your Dragon (2010).mkv")[1], "movie")
        self.assertEqual(rel("Training Day (2001).mkv")[1], "movie")
        self.assertEqual(rel("Sams.Sandwiches.S15E01.1080p.mkv")[1], "tv")

    def test_small_tutorial_not_skipped_as_sample(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "AutoCAD 2025 - 3D Tutorial For Beginners!.mp4"
            f.write_bytes(b"x" * 1000)
            self.assertEqual(ks.plan_for(f, D)[1], "tutorial")
            g = Path(d) / "Some Film (2020).mp4"
            g.write_bytes(b"x" * 1000)
            self.assertIsNone(ks.plan_for(g, D)[0])


if __name__ == "__main__":
    unittest.main()
