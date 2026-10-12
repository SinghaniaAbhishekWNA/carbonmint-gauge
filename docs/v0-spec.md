# Water level image processing


This describes the detector in src/enhanced-detector.ts. It is the path WaterLevelProcessor uses for a drone photo of a Bowman pipe. The photo is a JPEG. The detector decodes it to RGB and counts the pink stripes on the gauge.


## What a reading is


Each stripe is 1 cm of water level. The reading in centimetres is the number of stripes, including stripes the detector infers where a regular gap is missing. The level relative to the guide is that count minus 10 cm. The guide zero sits 10 cm along the counted stripes.


The configured strip is 30 cm tall and 5 cm wide. A 30 cm strip with zero in the middle would run from −15 cm to +15 cm. This detector does not use that centering. Its zero is the 10 cm guide offset above. The configuration also records a maximum of 15 stripes. The counter does not stop at 15.


A photo with no stripe stack has no centimetre reading. Its confidence is 0.


## How a photo is read


### Find the pink pixels


A pixel counts as part of a stripe when it is dull pink or red. Red is a hue at or below 20 or at or above 330, with saturation at least 35 and value at least 50, and the red channel stronger than green and than blue. Magenta is a hue from 140 to 175, with saturation at least 40 and value at least 50.


### Find the gauge column


The pipe is a thin vertical object, so the detector does not look for red across the whole frame. It slides a narrow window across the width and keeps the window with the most pink pixels. The window is about 2% of the image width, and it is kept between 36 and 180 pixels. If the strongest column is pink along less than 2% of the image height, there is no gauge column and no reading.


### Turn pink rows into stripes


Inside that column, a row is part of a stripe when enough of the row is pink and the pink spans enough of the column. Consecutive pink rows, including rows separated by a gap of up to 3 pixels, are one stripe.


A kept stripe is a short solid bar. It is at least 5 pixels tall, at least 28% as wide as the column, and at least 45% filled with pink. A speck or a broad pink patch is dropped.


The detector then keeps the longest run of stripes whose gaps are on the scale of the gauge. A gap larger than about 4.5 times the typical tight spacing starts a new run. One stripe is enough to be a reading.


### Stripe distance


The physical distance represented by one stripe is 1 cm. In the image, the distance between stripes is measured from the photo.


The pitch is the median distance between the centers of neighboring visible stripes. Gaps that are already at least 1.7 times the current pitch are left out of that median, and the median is refined for up to four passes. One wide hole therefore does not stretch the pitch used to judge the next hole.


On a 5 cm wide pipe, a single stripe is about 1 cm tall. The detector uses that ratio on each bar: expected height is the bar’s width times 1/5. A bar up to 2.5 times that tall scores as one stripe. A taller bar scores as stripes that have run together, or as a pink patch, and it lowers the confidence.


### Stripes that are hidden


A leaf, a stain, or a soft edge can hide a stripe while the stripes above and below it stay visible. The detector fills that hole from the pitch of the stripes it can see.


A gap at least 1.65 times the pitch is a hidden stretch. The number of hidden stripes is the gap divided by the pitch, rounded, minus one. A gap of two pitches hides one stripe. A gap of three pitches hides two. Those stripes are added to the centimetre count. They are not drawn as detected bars.


Each such hole also lowers confidence. The factor is 1 − 0.1 × number of holes, and it does not go below 0.5. A hole that was filled this way is left out of the spacing variation, so the same hole is not punished twice.


### Confidence


Confidence is a score from 0 to 1. It is the product of four factors:


1. Spacing. One stripe has no gap to judge, so this factor is 1. Two or more stripes use 1 − coefficient of variation of the visible gaps, and the factor does not go below 0.3. Uneven gaps lower the score. Hidden-stripe gaps are not part of that variation.
2. Inferred stripes, as above.
3. How solid each stripe is. A pink row is scored against 45% of the column width, and a stripe keeps the best row in that stripe. The factor is the average of those scores. A separate check drops a bar whose whole rectangle is under 45% pink.
4. Thickness, as above. The factor is the average of the per-stripe thickness scores. A bar that is too thick contributes 0.25 instead of 1.


A folder accepts a photo when its confidence is at least 0.7 and it has a centimetre reading. One such photo is enough. The folder level is the average of those photos. A folder with none of them stays in review.


### Soil state


The state uses the level relative to the guide, in centimetres:


| Relative level | State |
| --- | --- |
| Above +2 | Flooded |
| −2 to +2 | Saturated |
| −12 inclusive, below −2 | Drying |
| Below −12 | Irrigate now |


## Problem statement


Drone photos of a stripe gauge are read as a water level in centimetres. A photo is accepted when the system’s confidence that the reading is accurate is greater than 0.7. Every other photo stays out of the accepted set.


On photos of a correct gauge tested so far, about half reach that bar. Of the drone photos that show a correct gauge, 70–80% need to reach it. Photos of a bad gauge are not part of that rate.


Photos that already score above 0.7 stay as they are. The gap is the rest of the correct-gauge photos: the stripes look too close together or too thick, the drone is not square to the gauge, or the weather or the general visibility is poor. In those photos the count is missed, or the count is right and the confidence stays at or below 0.7.


A bad gauge is reported with a confidence score at or below 0.7 and a note that the gauge is bad. The system does not produce an accepted centimetre reading for it.


A higher score on a wrong centimetre reading does not meet the goal. A correct-gauge photo counts toward the 70–80% only when its accepted reading is an accurate reading of that gauge.


How the reading is improved, and whether that runs in the scheduled batch, the upload page, or both, is not part of this statement.