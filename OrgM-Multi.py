'''
        OrgM-Multi: Organoid Counter and Size Measurer            - ImageJ Macro written in Python 
'''

# Import required packages

import os, sys, math, datetime
from ij import IJ, ImagePlus
from ij.io import DirectoryChooser
from ij.measure import ResultsTable, Measurements
from ij.process import ImageConverter
from ij.gui import WaitForUserDialog
from ij.gui import GenericDialog, TextRoi
from ij.plugin.frame import RoiManager
from ij.plugin.filter import ParticleAnalyzer

# ---------------------------
# OPTIONS
# ---------------------------

thresholdMode = False
gd = GenericDialog("Set Threshold Mode")
gd.addChoice("Would you like to enable thresholding mode?", ["Yes, enable thresholding mode", "No, run the normal macro"], "Yes, enable thresholding mode")
gd.showDialog()
if gd.getNextChoice() == "Yes, enable thresholding mode":
    thresholdMode = True

watershedMode = False
gd = GenericDialog("Set Watershed Mode")
gd.addChoice("Would you like to enable watershedding?", ["No, do not watershed", "Yes, enable watershed"], "No, do not watershed")
gd.showDialog()
if gd.getNextChoice() == "Yes, enable watershed":
    watershedMode = True

inverted = False
gd = GenericDialog("Set Invert Mode")
gd.addChoice("", ["Dark organoid on light background", "Light organoid on dark background"], "Dark organoid on light background")
gd.showDialog()
if gd.getNextChoice() == "Light organoid on dark background":
    inverted = True
    
# Set default thresholds
#	round_threshold is the minimum roundness a roi must have to be considered an organoid and counted as a valid ROI
#	area_threshold is the minimum area a roi must have to be considered an organoid and counted as a valid ROI
#	minimum_size is the minimum area to be considered an ROI in ParticleAnalyzer
#   area_threshold and minimum_size are in particles. This will need to be determined for your specific use case. For us, 6000 pixels represents an object with 100 micron diameter

round_threshold = 0.33
area_threshold = 6000
minimum_size = 6000

gd = GenericDialog("Dimension Options")
gd.addMessage("Evos 10X  = 0.8777017 px/uM")
gd.addMessage("Evos 4X  = 2.1546047 px/uM")
gd.addChoice("Choose the pixel scale of your image:", ["10X Evos", "4X Evos", "Other"], "10X Evos")
gd.showDialog()
choice = gd.getNextChoice()

if choice == "10X Evos":
    pix_width = 0.8777017
    pix_height = 0.8777017
elif choice == "4X Evos":
    pix_width = 2.1546047
    pix_height = 2.1546047
else:
    gd = GenericDialog("Dimension Options")
    gd.addMessage("Enter pixel dimensions:")
    gd.addStringField("Pixel Width:", "0.8777017")
    gd.addStringField("Pixel Height:", "0.8777017")
    gd.showDialog()
    pix_width = float(gd.getNextString())
    pix_height = float(gd.getNextString())

# ---------------------------
# INPUT / OUTPUT
# ---------------------------

dc = DirectoryChooser("Choose an input directory")
inputDirectory = dc.getDirectory()

dc = DirectoryChooser("Choose an output directory")
outputDirectory = dc.getDirectory()

roiImageDir = os.path.join(outputDirectory, "ROI_Images")
if not os.path.exists(roiImageDir):
    os.makedirs(roiImageDir)

outpath = os.path.join(outputDirectory, "output_" + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M") + ".csv")

with open(outpath, "w") as output:

    output.write("Subfolder,File Name,ROI Index,NumOrganoids,Feret,MinFeret,Average Feret,Area,Equivalent Circle Diameter,Major,Minor,Circularity,Roundness,Solidity,MeetsCriteria\n")

    subfolders = []
    for subfolder in os.listdir(inputDirectory):
        if os.path.isdir(os.path.join(inputDirectory, subfolder)):
            subfolders.append(subfolder)

    if len(subfolders) == 0:
        subfolders = [""]

    for subfolder in subfolders:
        folder_path = os.path.join(inputDirectory, subfolder)

        for filename in os.listdir(folder_path):

            imp_path = os.path.join(folder_path, filename)
            imp = IJ.openImage(imp_path)
            if not imp:
                continue

            IJ.run(imp, "Properties...", "unit=um pixel_width=" + str(pix_width) + " pixel_height=" + str(pix_height))

            ic = ImageConverter(imp)
            ic.convertToGray8()
            IJ.setAutoThreshold(imp, "Default dark")

            if thresholdMode:
                imp.show()
                IJ.run("Threshold...")
                WaitForUserDialog("Adjust threshold", "Click OK when ready").show()

            IJ.run(imp, "Convert to Mask", "")
            if not inverted:
                try:
                    IJ.run(imp, "Invert", "")
                except:
                    print("Warning: Could not invert image, skipping invert.")
            IJ.run(imp, "Fill Holes", "")
            if watershedMode:
                IJ.run(imp, "Watershed", "")

            table = ResultsTable()
            roim = RoiManager(True)
            ParticleAnalyzer.setRoiManager(roim)

            pa = ParticleAnalyzer(
                ParticleAnalyzer.ADD_TO_MANAGER | ParticleAnalyzer.EXCLUDE_EDGE_PARTICLES,
                Measurements.AREA | Measurements.FERET | Measurements.CIRCULARITY | Measurements.SHAPE_DESCRIPTORS | Measurements.ELLIPSE,
                table,
                minimum_size,
                9e15,
                0.2,
                1.0
            )
            pa.setHideOutputImage(True)
            pa.analyze(imp)

            # ============================
            # FILTER ROIs BY BIOLOGICAL CRITERIA
            # You can filter ROIs by biological criteria, including area, roundness and circularity
            # ============================

            valid_indices = []
            for i in range(table.size()):
                area = table.getValue("Area", i)
                roundness = table.getValue("Round", i)
                circularity = table.getValue("Circ.", i)
                if (area > area_threshold) and (roundness > round_threshold) and (circularity <=1):
                    valid_indices.append(i)

            numOrganoids = len(valid_indices)

            # -----------------------
            # SAVE ROI ANNOTATED IMAGE WITH NUMBERS
            # -----------------------

            annot = IJ.openImage(imp_path)
            annot.show()

            for j, idx in enumerate(valid_indices):
                roim.select(idx)
                # Draw ROI outline
                IJ.run(annot, "Draw", "")
                # Draw numbers
                roi = roim.getRoi(idx)
                if roi is not None:
                    bounds = roi.getBounds()
                    x = bounds.x
                    y = bounds.y - 2
                    tr = TextRoi(x, y, str(j + 1))
                    annot.setRoi(tr)
                    IJ.run(annot, "Draw", "")

            IJ.run(annot, "Flatten", "")
            savePath = os.path.join(roiImageDir, filename.replace(".tif", "_ROIs.png"))
            IJ.saveAs(annot, "PNG", savePath)
            annot.close()

            # -----------------------
            # WRITE ROI DATA TO CSV
            # -----------------------

            if numOrganoids == 0:
                output.write(subfolder + "," + filename + ",NA,0," + ",".join(["NA"]*12) + "\n")
            else:
                for j, idx in enumerate(valid_indices):

                    area = table.getValue("Area", idx)
                    feret = table.getValue("Feret", idx)
                    minFeret = table.getValue("MinFeret", idx)
                    circ = table.getValue("Circ.", idx)
                    major = table.getValue("Major", idx)
                    minor = table.getValue("Minor", idx)

                    avgFeret = (feret + minFeret) / 2
                    diameter = 2 * math.sqrt(area / math.pi)

                    output.write(
                        str(subfolder) + "," +
                        filename + "," +
                        str(j + 1) + "," +
                        str(numOrganoids) + "," +
                        str(feret) + "," +
                        str(minFeret) + "," +
                        str(avgFeret) + "," +
                        str(area) + "," +
                        str(diameter) + "," +
                        str(major) + "," +
                        str(minor) + "," +
                        str(circ) + "," +
                        str(table.getValue("Round", idx)) + "," +
                        str(table.getValue("Solidity", idx)) + "," +
                        "True\n"
                    )

            imp.changes = False
            imp.close()
            roim.reset()
            roim.close()

# End of Script
