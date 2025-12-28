from merged import searchLikeThereIsNoTomorrow
import matplotlib.pyplot as plt

ResImage, SolutionList, VisitedList = searchLikeThereIsNoTomorrow("maze.png", RGBValues = [1,2,3], SolutionLength = 'inf')

print(SolutionList)
print(VisitedList)
plt.imshow(ResImage)
plt.show()