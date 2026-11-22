# Visualisation

Reference for principle 4 in [`SKILL.md`](SKILL.md). The rule: **the central
message to the audience should be immediately clear from the visualisation.**
This file covers *what a figure should say and how to make that readable*.
How it should *look* (fonts, palettes, plotting conventions) is aesthetics,
which is covered separately.

It is language-agnostic: the same ideas apply in Python, Julia, MATLAB, and R.

## State the point first

The same data can support many different figures, each emphasising a different
projection of it. No plot can show everything, so the first decision is not
*how* to plot but *what the panel is for*.

**The point is one sentence the panel should convey**, for example "silencing
region A and region B changes behavior by different amounts, in every subject".

- **As an agent, before you generate a plot, make sure the user (or project
  manager) has stated the point.** If they have not, ask. Do not guess and
  draw a default; a figure built without a point is a guess about what matters.
- **As a subagent you have no one to ask:** the point must be in your work
  item. If it is missing, return and say so instead of plotting.
- Write the point down. A general-purpose plotting function's docstring says
  when to use it ("Use this to compare X and Y across conditions"). A function
  that makes one specific manuscript panel states that panel's point ("We plot
  control animals in black and drug animals in red and zoom in on the first 10
  days of learning to emphasize the differences in early training"). Either
  way the point also goes in the figure legend or caption; it is what you and
  the reviewer check the figure against.
- One panel, one point. If you have two points, make two panels.
- If the point changes, the figure changes. Do not patch the old figure.

**How to ask.** If the request names no point (for example "make a figure for
the paper"), ask "what should a reader conclude from this panel?" and offer two
or three candidate one-sentence points drawn from the analysis for the user to
choose from. Do not answer with a default plot.

## Same data, different point, different figure

Take a silencing experiment in two brain regions, in a task with 20 trial
types. The same data supports very different figures:

- **Point: the effect differs between the two regions, and is reliable.**
  Reduce each session or subject to one metric (an average, or another summary
  of the effect), then plot the distribution of that metric for the two
  regions in a single panel. Using sessions or subjects as the unit shows
  robustness. If every subject contributed to both regions, show that: a
  scatter plot with one point per subject, and the metric in region A on one
  axis and in region B on the other.
- **Point: in region A, some trial types are influenced and others are not.**
  Now the trial type is the axis of interest, so the figure is a completely
  different one: the effect per trial type for region A, with its
  uncertainty, so that which trial types move and which do not is visible at
  a glance.

Neither figure is the "right" one for this dataset. Each is right for its
point, which is why the point has to come first.

## Make it easy to read

A figure that delivers its point **must be easily readable**. The ideal figure
is self-contained: a reader who sees only the figure and its caption gets the
message, without hunting through the text.

- **Fonts should be large.** Text that needs squinting at is not read. Check
  legibility at the size the figure will actually be shown or printed.
- **Colour should carry meaning.** If the data has a natural hierarchy,
  encode it. With two groups of five conditions, use light-to-dark blue for the
  five conditions of group 1 and light-to-dark red for the five of group 2: the
  group is read from the hue, and the order within the group from the shade.
  Do not assign colours arbitrarily when structure exists.
- **Annotate.** Labels placed on the data, a marked threshold, a short note
  pointing at the effect, or a sample size can all do more than a legend the
  reader must decode. Annotations are often the cheapest way to make a figure
  self-contained.
- **Use transparency to show variance honestly while the message stays
  striking.** Draw the individual sessions or subjects (the unit of
  replication) faint and translucent, and the summary the point is about
  (often the mean or median of a metric) bold and opaque on top. The reader
  sees both the spread and the message. Do not draw individual trials this
  way as if their spread were between-subject variance.

## Check the figure against the point

Before calling a figure done, look at it as the intended audience would, and
ask:

1. Is the point (see "State the point first") the first thing the eye lands
   on?
2. Is anything on the panel not serving that point? Remove it, or make it
   recede.
3. Could someone who has not read the text state the point from the figure and
   its caption alone?

If the answer to any of these is no, revise the figure; do not explain the
problem away in the text.
