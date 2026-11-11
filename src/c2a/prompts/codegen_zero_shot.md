Write the Manim code for one scene of an explainer video.

Video concept: $concept_name
Full storyboard (for context; implement only scene $scene_idx):
$storyboard_outline

Scene $scene_idx to implement:
- Title: $title
- Visual: $visual
- Narration (for timing only; do not add audio or subtitles): $narration

Requirements:
- Start with `from manim import *`.
- Define exactly one class named `$class_name` that subclasses `Scene`, with all animation in `construct(self)`.
- The visible frame is x from -$frame_x to $frame_x and y from -$frame_y to $frame_y. Keep every object fully inside it.
- Don't let objects overlap unless one is meant to be on top of another (like a label on a shape).
- Use only built-in Manim objects. Don't load images, SVGs, sounds or other files.
- Aim for roughly 10 to 20 seconds of animation.
