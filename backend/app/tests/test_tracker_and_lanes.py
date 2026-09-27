import unittest

from app.services.cv.tracker import CentroidIoUTracker, Detection
from app.services.cv.lane_assigner import LaneAssigner, LanePolygon, point_in_polygon, UNKNOWN_LANE


class TestPointInPolygon(unittest.TestCase):
    def test_inside_square(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(point_in_polygon((5, 5), square))

    def test_outside_square(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertFalse(point_in_polygon((50, 50), square))


class TestCentroidIoUTracker(unittest.TestCase):
    def test_same_vehicle_keeps_same_id_across_frames(self):
        tracker = CentroidIoUTracker()
        d1 = Detection(bbox=(100, 100, 140, 160), class_name="car", confidence=0.9)
        tracks_f1 = tracker.update([d1])
        self.assertEqual(len(tracks_f1), 1)
        first_id = tracks_f1[0].track_id

        # vehicle moves slightly - should match the same track, not spawn a new one
        d2 = Detection(bbox=(105, 100, 145, 160), class_name="car", confidence=0.88)
        tracks_f2 = tracker.update([d2])
        self.assertEqual(len(tracks_f2), 1)
        self.assertEqual(tracks_f2[0].track_id, first_id)

    def test_new_vehicle_entering_gets_new_id(self):
        tracker = CentroidIoUTracker()
        d1 = Detection(bbox=(100, 100, 140, 160), class_name="car", confidence=0.9)
        tracker.update([d1])

        d1_moved = Detection(bbox=(102, 100, 142, 160), class_name="car", confidence=0.9)
        d2_new = Detection(bbox=(500, 500, 540, 560), class_name="car", confidence=0.85)
        tracks = tracker.update([d1_moved, d2_new])
        self.assertEqual(len(tracks), 2)
        ids = {t.track_id for t in tracks}
        self.assertEqual(len(ids), 2)

    def test_occlusion_tolerance_keeps_track_alive(self):
        tracker = CentroidIoUTracker(max_missed_frames=3)
        d1 = Detection(bbox=(100, 100, 140, 160), class_name="car", confidence=0.9)
        tracker.update([d1])
        first_id = tracker.active_tracks[0].track_id

        # vehicle occluded for 2 frames (no detection) - should not be dropped
        tracker.update([])
        tracker.update([])
        self.assertIn(first_id, tracker._tracks)

        # reappears close to where it was - should re-match, not spawn a new id
        d_reappear = Detection(bbox=(108, 100, 148, 160), class_name="car", confidence=0.9)
        tracks = tracker.update([d_reappear])
        self.assertEqual(tracks[0].track_id, first_id)

    def test_track_dropped_after_exceeding_missed_frames(self):
        tracker = CentroidIoUTracker(max_missed_frames=2)
        d1 = Detection(bbox=(100, 100, 140, 160), class_name="car", confidence=0.9)
        tracker.update([d1])
        first_id = tracker.active_tracks[0].track_id

        tracker.update([])
        tracker.update([])
        tracker.update([])  # 3rd consecutive miss > max_missed_frames=2
        self.assertNotIn(first_id, tracker._tracks)

    def test_reset_clears_all_state(self):
        tracker = CentroidIoUTracker()
        tracker.update([Detection(bbox=(0, 0, 10, 10), class_name="car", confidence=0.9)])
        tracker.reset()
        self.assertEqual(len(tracker._tracks), 0)
        tracks = tracker.update([Detection(bbox=(0, 0, 10, 10), class_name="car", confidence=0.9)])
        self.assertEqual(tracks[0].track_id, 1)  # id counter restarted


class TestLaneAssigner(unittest.TestCase):
    def setUp(self):
        self.north_lane = LanePolygon(
            lane_id="NORTH", direction="NORTH", polygon=[(0, 0), (100, 0), (100, 100), (0, 100)]
        )
        self.assigner = LaneAssigner([self.north_lane], fps=25.0)

    def test_vehicle_inside_polygon_gets_correct_lane(self):
        tracker = CentroidIoUTracker()
        tracks = tracker.update([Detection(bbox=(40, 40, 60, 60), class_name="car", confidence=0.9)])
        assignment = self.assigner.assign(tracks[0], frame_index=1)
        self.assertEqual(assignment.lane_id, "NORTH")

    def test_vehicle_outside_all_polygons_is_unknown(self):
        tracker = CentroidIoUTracker()
        tracks = tracker.update([Detection(bbox=(900, 900, 920, 920), class_name="car", confidence=0.9)])
        assignment = self.assigner.assign(tracks[0], frame_index=1)
        self.assertEqual(assignment.lane_id, UNKNOWN_LANE)

    def test_stopped_vehicle_flagged_and_waiting_time_accrues(self):
        tracker = CentroidIoUTracker()
        # vehicle stays in the same spot across frames -> considered stopped
        for frame in range(1, 26):  # 25 frames = 1 second at fps=25
            tracks = tracker.update([Detection(bbox=(40, 40, 60, 60), class_name="car", confidence=0.9)])
            assignment = self.assigner.assign(tracks[0], frame_index=frame)
        self.assertTrue(assignment.is_stopped)
        self.assertGreater(assignment.waiting_time_s, 0)

    def test_moving_vehicle_not_flagged_as_stopped(self):
        tracker = CentroidIoUTracker()
        assignment = None
        for frame, x in enumerate(range(40, 90, 10), start=1):
            tracks = tracker.update([Detection(bbox=(x, 40, x + 20, 60), class_name="car", confidence=0.9)])
            assignment = self.assigner.assign(tracks[0], frame_index=frame)
        self.assertFalse(assignment.is_stopped)
        self.assertGreater(assignment.speed_kmph, 0)


if __name__ == "__main__":
    unittest.main()
