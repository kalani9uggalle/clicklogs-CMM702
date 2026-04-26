/**
 * CMM702 Advanced Databases — Part B, Question 2
 * MongoDB Aggregation Queries on tap_logs collection
 *
 * Assumption: Firestore data has been exported to MongoDB
 * into a collection called 'tap_logs'.
 *
 * Each document structure:
 * {
 *   session_id:         "1712345678123_42",
 *   device:             "android" | "pc",
 *   tap_sequence:       1..50,
 *   start_timestamp:    1712345678123,
 *   end_timestamp:      1712345678201,
 *   duration:           78,
 *   interface_type:     "feedbackshown" | "nofeedback",
 *   interface_sequence: 1 | 2,
 *   created_at:         ISODate(...)
 * }
 */

// ── Query a ───────────────────────────────────────────────────────────────────
// Calculate the mean tap duration for Android vs PC users

db.tap_logs.aggregate([
  {
    $group: {
      _id: "$device",                        // group by device: "android" or "pc"
      mean_duration_ms: { $avg: "$duration" } // average duration in milliseconds
    }
  },
  {
    $project: {
      _id: 0,
      device:           "$_id",
      mean_duration_ms: { $round: ["$mean_duration_ms", 2] }
    }
  },
  {
    $sort: { device: 1 }
  }
]);

/*
 * Expected output:
 * { device: "android", mean_duration_ms: 145.32 }
 * { device: "pc",      mean_duration_ms: 98.17  }
 */


// ── Query b ───────────────────────────────────────────────────────────────────
// Compare average tap duration between "feedbackshown" vs "nofeedback" interfaces

db.tap_logs.aggregate([
  {
    $group: {
      _id: "$interface_type",               // group by interface: feedbackshown | nofeedback
      avg_duration_ms: { $avg: "$duration" }
    }
  },
  {
    $project: {
      _id: 0,
      interface_type:  "$_id",
      avg_duration_ms: { $round: ["$avg_duration_ms", 2] }
    }
  },
  {
    $sort: { interface_type: 1 }
  }
]);

/*
 * Expected output:
 * { interface_type: "feedbackshown", avg_duration_ms: 132.45 }
 * { interface_type: "nofeedback",    avg_duration_ms: 118.73 }
 */


// ── Query c ───────────────────────────────────────────────────────────────────
// How many users completed both interface variations vs dropped off after the first?
//
// Logic:
//   - Each session has 2 interface_sequence values (1 and 2).
//   - If a session has documents for BOTH interface_sequence 1 AND 2 → completed both.
//   - If a session only has interface_sequence 1 → dropped off after first.

db.tap_logs.aggregate([
  {
    // Step 1: per session, collect the distinct interface_sequence values seen
    $group: {
      _id: "$session_id",
      sequences_seen: { $addToSet: "$interface_sequence" }
    }
  },
  {
    // Step 2: determine if the session completed both variations
    $project: {
      completed_both: {
        $eq: [{ $size: "$sequences_seen" }, 2]  // true if both 1 and 2 are present
      }
    }
  },
  {
    // Step 3: count sessions in each group (completed vs dropped off)
    $group: {
      _id: "$completed_both",
      session_count: { $sum: 1 }
    }
  },
  {
    // Step 4: readable output
    $project: {
      _id: 0,
      status: {
        $cond: {
          if:   "$_id",
          then: "completed_both_variations",
          else: "dropped_off_after_first"
        }
      },
      session_count: 1
    }
  },
  {
    $sort: { status: 1 }
  }
]);

/*
 * Expected output:
 * { status: "completed_both_variations",  session_count: 18 }
 * { status: "dropped_off_after_first",    session_count: 4  }
 */
