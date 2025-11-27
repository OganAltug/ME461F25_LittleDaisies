# NO LLM ASSISTANCE WAS TAKEN FOR THIS HOMEWORK, 
all sources and tools used are given in references below

# Q1 & Q2 
**What are unipolar and bipolar stepper?**
A unipolar stepper divides coils into two halves. This way it can just
activate the other half whenever it wants to reverse polarity of the coil. 
This means both halves of the coil can't be active simultaneously. On the 
other hand a bipolar stepper utilizes the whole coil and has to switch current
direction to reverse polarity. So unipolar is simpler to control compared to
bipolar.

Since bipolar utilizes the whole coil, it produces significantly higher torque
compared to unipolar. However, bigger coil also comes with higher inductance and 
bipolar steppers can't keep up with unipolar steppers at high RPMs due this reason.

**REFERENCES:**
- [Stepper Motor Wiring Basics: Unipolar vs Bipolar](https://blog.orientalmotor.com/stepper-motor-wiring-basics-unipolar-vs-bipolar)

# Q3 & Q4:
**What is the difference between half and full stepping?**
Full stepping is done by activating only a single coil for one step. This way
a step resolution of 360/N_coil is obtained. An example,
1000 -> 0100 -> 0010 -> 0001

If we also activate two sequential coils in addition to full stepping, we would
obtain new motor positions in middle of the full step positions. Basically halving 
the resolution by 2: 180/N_coil. Modifiying the previous example,
1000 -> 1100 -> 0100 -> 0110
-> 0010 -> 0011 -> 0001 -> 1001

Note: To keep the torque constant through the whole operation, we would also need to
supply 0.7071 times the nominal current for each coil when we activate two coils
at the same time. 
**How can you increase the resolution of a stepper beyond half-stepping?**
We can use micro stepping, similar to half stepping we can produce more steps by
varying the current supplied between two coils activated at the same time. And just 
like half-stepping, to keep torque constant we would need to make sure their squraes 
add up to nominal value.

Overall increasing step size gives smoother operation, less noise and vibrations. However,
at high rpm's shaft can struggles to keep up with smaller step differences and increasing 
step size can cause accuracy loss in motor position.

**REFERENCES:**
- [What is the difference between full-stepping, the half-stepping, and the micro-drive?](https://www.automate.org/motion-control/case-studies/what-is-the-difference-between-full-stepping-the-half-stepping-and-the-micro-drive)

# Q5:
**What is slew rate**
"In electronics, the slew rate is defined as the maximum rate of output voltage change per unit time." 
This metric basically measures the difference between a ideal unit step and the unit step a device can achive.
In our context this device could be the motor drivers user for stepper motors. If we increase stepping rate too much
our controller may not be able to keep up and fully activate coils of stepper if it's slew rate is lower than needed.

Another close in name but very different meaning metric is "slew range". Which defines the operation region described 
by stepping rate and load torque. In this region motor can keep up with all the step signals but can't reverse or start 
from rest without missing steps. We would need to slow the motor down and move to start range instead to perform these 
actions. Beyond slew range, motor always misses steps.

**REFERENCES:**
- [Advantage and Disadvantage of Stepper Motors:](https://www.eeeguide.com/advantage-and-disadvantage-of-stepper-motors/)

# Q6:
**What is the relation between torque and angular velocity (~ step rate)?**
Step rate and torque is inversely proportional and there is a significant drop off as angular velocity increases.
This related to the inductance inherited within the coils, which makes it very hard for current to flow with high 
frequencies.


