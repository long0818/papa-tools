from PyQt4.QtCore import *
from PyQt4.QtGui import *

import maya.cmds as cmds
import maya.OpenMayaUI as omu
from pymel.core import *
# import utilities as amu #asset manager utilities
import os
import sip
import Facade.facade as facade

WINDOW_WIDTH = 330
WINDOW_HEIGHT = 300

def maya_main_window():
	ptr = omu.MQtUtil.mainWindow()
	return sip.wrapinstance(long(ptr), QObject)		

class AlembicExportDialog(QDialog):
	def __init__(self, parent=maya_main_window()):
	#def setup(self, parent):
		QDialog.__init__(self, parent)
		self.saveFile()
		self.setWindowTitle('Select Objects for Export')
		self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
		self.create_layout()
		self.create_connections()
		self.create_export_list()
	
	def create_layout(self):
		#Create the selected item list
		self.selection_list = QListWidget()
		self.selection_list.setSelectionMode(QAbstractItemView.ExtendedSelection);
		self.selection_list.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

		#Create Export Alembic and Cancel buttons
		self.export_button = QPushButton('Export Alembic')
		self.cancel_button = QPushButton('Cancel')
		
		#Create button layout
		button_layout = QHBoxLayout()
		button_layout.setSpacing(2)
		button_layout.addStretch()
	
		button_layout.addWidget(self.export_button)
		button_layout.addWidget(self.cancel_button)
		
		#Create main layout
		main_layout = QVBoxLayout()
		main_layout.setSpacing(2)
		main_layout.setMargin(2)
		main_layout.addWidget(self.selection_list)
		main_layout.addLayout(button_layout)
		
		self.setLayout(main_layout)
	
	def create_connections(self):
		#Connect the buttons
		self.connect(self.export_button, SIGNAL('clicked()'), self.export_alembic)
		self.connect(self.cancel_button, SIGNAL('clicked()'), self.close_dialog)
	
	def create_export_list(self):
		#Remove all items from the list before repopulating
		self.selection_list.clear()
		
		#Add the list to select from
		loadedRef = self.getLoadedReferences()
		
		for ref in loadedRef:
			item = QListWidgetItem(ref) 
			item.setText(ref)
			self.selection_list.addItem(item)
		
		self.selection_list.sortItems(0)
	
	def getLoadedReferences(self):
		references = cmds.ls(references=True)
		loaded=[]
		print "Loaded References: "
		for ref in references:
			print "Checking status of " + ref
			try:
				if cmds.referenceQuery(ref, isLoaded=True):
					loaded.append(ref)
			except:
				print "Warning: " + ref + " was not associated with a reference file"
		return loaded
	
	
	########################################################################
	# SLOTS
	########################################################################
	def export_alembic(self):
		self.saveFile()
		
		selectedReferences = []
		selectedItems = self.selection_list.selectedItems()
		for item in selectedItems:
			selectedReferences.append(item.text())
		print "Here are the references: ", selectedReferences

		if self.showConfirmAlembicDialog(selectedReferences) == 'Yes':
			loadPlugin("AbcExport")
			for ref in selectedReferences:
				filePath = cmds.file(q=True, sceneName=True)
				refPath = cmds.referenceQuery(unicode(ref), filename=True)
				abcFilePath = facade.build_alembic_filepath(self, refPath, filePath) # This needs to be moved into the facade/alembic exporter.
				print "abcFilePath", abcFilePath
				command = self.build_alembic_command(ref, abcFilePath)
				print "Export Alembic command: ", command
				Mel.eval(command)
		
		self.close_dialog()
	
	def saveFile(self):
		if not cmds.file(q=True, sceneName=True) == '':
			cmds.file(save=True, force=True) #save file
	
	def showConfirmAlembicDialog(self, references):
		return cmds.confirmDialog( title         = 'Export Alembic'
		                         , message       = 'Export Alembic for:\n' + str(references)
		                         , button        = ['Yes', 'No']
		                         , defaultButton = 'Yes'
		                         , cancelButton  = 'No'
		                         , dismissString = 'No')
	
	# def build_alembic_filepath(self, ref):
	# 	# This builds the location where the alembic file will be stored. This definitely needs to be moved.
	# 	#Get Shot Directory
	# 	filePath = cmds.file(q=True, sceneName=True)
	# 	toCheckin = os.path.join(amu.getUserCheckoutDir(), os.path.basename(os.path.dirname(filePath)))
	# 	dest = amu.getCheckinDest(toCheckin)
		
	# 	#Get Asset Name
	# 	refPath = cmds.referenceQuery(unicode(ref), filename=True)
	# 	assetName = os.path.basename(refPath).split('.')[0]
		
	# 	return os.path.join(os.path.dirname(dest), 'animation_cache', 'abc', assetName+'.abc')

	def build_alembic_command(self, ref, abcfilepath):
		# First check and see if the reference has a tagged node on it.
		tagged = self.get_tagged_node(ref)

		if tagged == "":
			return ""

		# Then we get the dependencies of that item to be tagged.
		depList = self.get_dependancies(ref)

		# Not sure yet what roots_string is for. Figure out.
		roots_string = ""
		roots_string = " ".join([roots_string, "-root %s"%(tagged.name())])


		# But it seems we add the dependencies to the thing being exported.
		for dep in depList:
			depRef = ls(dep)
			if len(depRef) > 0:
				tagged = self.get_tagged_node(depRef[0]).name()
			else:
				tagged = dep[:-2]

			roots_string = " ".join([roots_string, "-root %s"%(tagged)])

		start_frame = cmds.playbackOptions(q=1, animationStartTime=True) - 5
		end_frame = cmds.playbackOptions(q=1, animationEndTime=True) + 5

		# Then here is the actual Alembic Export command for Mel.
		command = 'AbcExport -j "%s -frameRange %s %s -step 0.25 -writeVisibility -nn -uv -file %s"'%(roots_string, str(start_frame), str(end_frame), abcfilepath)
		return command

	def get_tagged_node(self, ref):
		# Looks for a tagged node that has the BYU Alembic Export flag on it.
		refNodes = cmds.referenceQuery(unicode(ref), nodes=True)
		rootNode = ls(refNodes[0])
		if rootNode[0].hasAttr("BYU_Alembic_Export_Flag"):
			taggedNode = rootNode[0]
		else:
			# Otherwise get the tagged node that is in the children.
			taggedNode = self.get_tagged_children(rootNode[0])

		if taggedNode == "":
			self.showNoTagFoundDialog(unicode(ref))
			return ""

		print "taggedNode ", taggedNode
		return taggedNode

	def get_tagged_children(self, node):
		# Too bad this is similar to the get_tagged_node method. Maybe this could be combined...
		for child in node.listRelatives(c=True):
			if child.hasAttr("BYU_Alembic_Export_Flag"):
				return child
			else:
				taggedChild = self.get_tagged_children(child)
				if taggedChild != "":
					return taggedChild
		return ""

	def get_dependancies(self, ref):
		# Looks like the 
		refNodes = cmds.referenceQuery(unicode(ref), nodes=True)
		rootNode = ls(refNodes[0])
		depList = self.get_dependant_children(rootNode[0])

		return depList

	def get_dependant_children(self, node):
		depList = []
		for const in node.listRelatives(ad=True, type="parentConstraint"):
			par = const.listRelatives(p=True)
			constNS = par[0].split(':')[0]
			targetList = cmds.parentConstraint(unicode(const), q=True, tl=True)
			targetNS = targetList[0].split(':')[0]
			if constNS != targetNS and targetNS not in depList:
				depList.append(targetNS + 'RN')

		print 'depList: ', depList
		return depList

	def showNoTagFoundDialog(self, ref):
		return cmds.confirmDialog( title         = 'No Alembic Tag Found'
		                         , message       = 'Unable to locate Alembic Export tag for ' + ref + '.'
		                         , button        = ['OK']
		                         , defaultButton = 'OK'
		                         , cancelButton  = 'OK'
		                         , dismissString = 'OK')
	
	def close_dialog(self):
		self.close()

def go():
	dialog = AlembicExportDialog()
	dialog.show()
	
if __name__ == '__main__':
	go()
