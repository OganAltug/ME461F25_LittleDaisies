# Image Generator & Solver

## 1\. Problem Description

This project implements a dual-purpose computer vision tool designed for Mechatronics applications. It addresses the challenge of creating robust image processing algorithms that can handle imperfect, noisy real-world data.

The application performs two primary tasks:

1.  **Synthetic Data Generation:**
      * Generates a scene with 10-15 random objects on a white background.
      * **Objects:** Shapes (Star, Rectangle, Triangle), Sizes (Small, Medium, Large), and Colors (Configurable).
      * **Noise Simulation:** Introduces realistic imperfections to test algorithm robustness.
          * *Color Noise:* Deviations in pixel intensity (e.g., Gaussian noise or Salt & Pepper).
          * *Shape Noise:* Geometric imperfections (e.g., Vertex Jitter, Aspect Ratio Distortion).
2.  **Automated Solving (Image Processing):**
      * Processes the generated image to detect and classify every object.
      * Assigns a unique 3-digit ID **(XYZ)** to each object:
          * **X:** Object Shape ID
          * **Y:** Size ID
          * **Z:** Color ID
      * Generates a labeled output image with a dynamic legend.

-----

## 2\. Methodology & Implementation

The solution strictly adheres to standard computer vision techniques (using OpenCV) as described in the lecture notes.

### A. Pre-processing

  * **Grayscale Conversion:** The image is converted to grayscale to simplify segmentation.
  * **Noise Reduction:** If "Salt & Pepper" noise is high, a median blur is applied to preserve edges while removing local extrema.
  * **Thresholding:** Inverse Binary Thresholding is used to separate the dark objects from the light background, creating a binary mask.

### B. Feature Extraction (The Solver)

The algorithm iterates through every contour found in the binary mask and calculates properties to classify the object.

#### 1\. Size Detection (ID: Y)

  * **Method:** **Area ($A$)** calculation.
  * **Logic:** The pixel area of the contour is calculated using spatial moments.
      * $A = \sum \sum B[i,j]$
  * **Classification:** Thresholds are scaled dynamically based on the image resolution ($Scale^2$).
      * $Area > Threshold_{Large} \rightarrow$ **Large (1)**
      * $Area > Threshold_{Medium} \rightarrow$ **Medium (2)**
      * $Else \rightarrow$ **Small (3)**

#### 2\. Shape Detection (ID: X)

  * **Method:** **Compactness ($C$)**.
  * **Logic:** Compactness is a dimensionless quantity invariant to scale and rotation.
      * $C = \frac{Perimeter^2}{Area}$
  * **Classification:**
      * $C \approx 4\pi (12.6)$ $\rightarrow$ **Circle**
      * $C \approx 16$ $\rightarrow$ **Rectangle** (Square-like)
      * $C \approx 20-25$ $\rightarrow$ **Triangle**
      * $C > 35$ $\rightarrow$ **Star** (High perimeter relative to area)

#### 3\. Color Detection (ID: Z)

  * **Method:** **Mean Intensity & Euclidean Distance**.
  * **Logic:**
    1.  A mask is created for the specific object.
    2.  The mean BGR (Blue, Green, Red) value of pixels inside the mask is computed.
    3.  The Euclidean distance is calculated between this mean color and the database of known reference colors.
    4.  The object is assigned the ID of the closest matching color.

#### 4\. Positioning

  * **Method:** **Centroid** calculation.
  * **Logic:** The geometric center (centroid) is derived from image moments.
      * $\bar{x} = \frac{M_{10}}{M_{00}}, \bar{y} = \frac{M_{01}}{M_{00}}$
  * This coordinate is used to place the identification tag `XYZ` on the image.

-----

## 3\. User Manual

### Installation

Ensure you have Python installed with the necessary libraries:

```bash
pip install opencv-python numpy pillow
```

### GUI Overview

The interface is split into a **Settings Panel (Left)** and a **Preview Area (Right)**.

#### Step 1: Configuration

1.  **Resolution:** Select your target image size (e.g., 1920x1080).
2.  **Preview Zoom:** Use the slider to resize the GUI preview images to fit your monitor (does not affect the saved file size).
3.  **ID Mappings:**
      * Assign which Shape (Star, Rect, Triangle) corresponds to ID 1, 2, or 3.
      * Assign which Color (Red, Purple, Cyan, etc.) corresponds to ID 1, 2, or 3.
4.  **Noise Settings:**
      * **Color Noise:** Drag the slider to add pixel noise (Gaussian or Salt & Pepper).
      * **Shape Noise:** Drag the slider to deform objects (Vertex Jitter makes lines wiggly; Distortion squashes shapes).

#### Step 2: Generation

1.  Click **"1. Generate New Scene"**.
      * This creates a random arrangement of objects in memory.
      * The "Generated Image Preview" will show a **Clean (Ground Truth)** version of the scene.
2.  (Optional) Adjust Noise Sliders and click **"2. Apply Noise to Scene"**.
      * This updates the preview to show the noisy version without moving the objects.
      * Use the **"Show Undistorted"** button to toggle between the Clean and Noisy views for comparison.

#### Step 3: Solving

1.  Click **"Process (Solve)"**.
      * The algorithm analyzes the currently visible noisy image.
      * A result image appears in the right panel with:
          * Contours drawn around detected objects.
          * `XYZ` tags placed on object centers.
          * A dynamic legend appended to the bottom of the image explaining the codes.

#### Step 4: Saving

1.  Click **"Save All Images"**.
2.  Choose a location and filename. The app will save three files:
      * `filename.jpg` (The Noisy Input)
      * `filename_ground_truth.jpg` (The Clean Reference)
      * `filename_solved.jpg` (The Processed Result with Legend)