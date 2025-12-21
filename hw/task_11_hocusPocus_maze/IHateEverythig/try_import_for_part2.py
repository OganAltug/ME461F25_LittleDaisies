from merged import searchLikeThereIsNoTomorrow
import matplotlib.pyplot as plt

ResImage, SolutionList, VisitedList = searchLikeThereIsNoTomorrow("maze.png", RGBValues = [1,2,3], SolutionLength = 'inf')

plt.imshow(ResImage)
plt.show()