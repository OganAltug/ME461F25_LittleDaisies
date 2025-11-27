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
<!-- - [text](https://www.mouser.com/blog/unipolar-vs-bipolar-drive-for-stepper-motors)
- [text](https://www.omc-stepperonline.com/support?journal_blog_post_id=127)
- [text](https://techexplorations.com/guides/arduino/motors/unipolar-vs-bipolar-stepper-motors/) -->

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

**REFERENCES:**
- [What is the difference between full-stepping, the half-stepping, and the micro-drive?](https://www.automate.org/motion-control/case-studies/what-is-the-difference-between-full-stepping-the-half-stepping-and-the-micro-drive)

**REFERENCES:**
- [text]()
- [text]()
- [text]()
- [text]()

