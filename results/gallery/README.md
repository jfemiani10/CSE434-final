# Midterm gallery

Sample videos from run `midterm_2026-11-13` (Gemini 3.5 Flash, rendered at 480p15). Each video is a whole concept: its scenes from the `zero_shot_repair` condition, stitched in order. All 20 scenes rendered in that condition. There's no narration yet; the audio track comes later.

| Video | Tier | Scenes | Repairs needed | Correctness (1–5) | Clarity (1–5) |
|---|---|---|---|---|---|
| [Pythagorean theorem](pythagorean_theorem__zero_shot_repair.mp4) | concrete | 4 | 0 | 5.0 | 4.1 |
| [Derivative as slope](derivative_as_slope__zero_shot_repair.mp4) | concrete | 3 | 2 | 4.8 | 4.5 |
| [Matrix multiplication](matrix_multiplication__zero_shot_repair.mp4) | structural | 3 | 5 | 3.5 | 1.8 |
| [Binary search](binary_search__zero_shot_repair.mp4) | structural | 3 | 0 | 5.0 | 4.3 |
| [Recursion](recursion__zero_shot_repair.mp4) | abstract | 3 | 1 | 5.0 | 4.5 |
| [Big-O notation](big_o_notation__zero_shot_repair.mp4) | abstract | 4 | 1 | 4.2 | 4.1 |

Scores are the mean of both raters (Jonah, Koray), rated blind to condition, averaged over the concept's scenes.

**A failure case:** [`matrix_multiplication_scene1__zero_shot__rendered_but_wrong.mp4`](matrix_multiplication_scene1__zero_shot__rendered_but_wrong.mp4). It rendered on the first try with no error, but both raters scored it 2/5 for correctness: there's no operator between A and B, the brackets don't match, and C is an empty dashed grid. This is why the study uses human ratings as well as render success.

**Chart:** [`midterm_success_by_tier.png`](midterm_success_by_tier.png) shows render success by tier for both conditions.

Every prompt, all generated code and all repair attempts for this run can be browsed with `python experiments/review.py midterm_2026-11-13` after running the pipeline (or in the shared review bundle). The numbers are in `results/tables/midterm_*.csv` and in Table 1 of the midterm report (`report/midterm/Femiani_Bayram_Midterm_Report.pdf`).
