import bpy
import eos
import numpy as np
import bmesh
from enum import Enum
import os.path
import mathutils

from numpy import random

maxSlider = 20

bl_info  = {
    "name" : "Eos Interface",
    "blender" : (2,80,0),
    "catagory" : "Eos"
}

class ShapeKeeper(): # Stores model data for currently selected model
    base = ""
    modelPath = ""
    blendShapePath = ""
    leftEye = ""
    rightEye = ""

class SliderType(Enum):
    Shape = 0
    Colour = 1
    Expression = 2

aShapeKeeper = ShapeKeeper() # Only one script is loaded so a object was needed

def getChildren(obj): # Get the children of the object
    children = []
    for ob in bpy.data.objects:
        if(ob.parent == obj):
            children.append(ob)

    return children

def getCoefficients(o): # return a 2D list containing all of the coefficients Shape, Colour, Expression

    shapeCount = o.my_settings.ShapeCount
    colourCount = o.my_settings.ColourCount
    expressionCount = o.my_settings.ExpressionCount

    if len(o.sliders.sliderList) < shapeCount + colourCount + expressionCount : return # If the sliders haven't been created yet return None

    me = [[0.0]* shapeCount, [0.0]* colourCount, [0.0]* expressionCount]

    for x in range(0,shapeCount):           
        me[0][x] =  o.sliders.sliderList[x].value
    
    for x in range(shapeCount,shapeCount + colourCount):
        me[1][x - shapeCount] =  o.sliders.sliderList[x].value

    for x in range(shapeCount + colourCount,shapeCount + colourCount + expressionCount): # Sliders are stored in a 1D list
        me[2][x - shapeCount - colourCount] =  o.sliders.sliderList[x].value


    return me

def refreshColoursBM(mesh, coloursLocation, colours, shouldSmooth, shouldDelete): # Refresh colours using the BM mesh instead of normal mesh (much faster)

    bm = bmesh.new()
    bm.from_mesh(mesh)

    if not bm.loops.layers.color:
        bm.loops.layers.color.new("color")

    colour_layer =  bm.loops.layers.color['color']

    i = 0
    x = 0

    for face in bm.faces:

        vertexLocation = coloursLocation[x] # Get colours stored as [x,y,z] from eos list
        face.smooth = shouldSmooth # Smooth each face if needed

        i = 0
        for loop in face.loops: # Loop each vertex (not always triangulated)
            color = [colours[vertexLocation[i]][0],colours[vertexLocation[i]][1],colours[vertexLocation[i]][2],1.0] # Must include alpha
            loop[colour_layer] = color
            i += 1
           
        x += 1

    if(shouldDelete):

        deletionVerts = getdeletionVerts()    

        if(not deletionVerts == None):

            deleteVerts(bm, deletionVerts)

    bm.to_mesh(mesh) # Convert bmesh back to blender mesh

    return None

def getdeletionVerts(): # Load the file and collect vertices into a usable list

    scene = bpy.context.scene
    obj = bpy.context.object

    fileName = obj.my_settings.VertexFileName
    filePath = scene.global_setting.GlobalVertexStore

    if(not os.path.isfile(filePath + fileName)): return # Return None if file doesn't exist

    f = open(filePath + fileName, "r")
    
    line = f.readline()
    line = line.split(",")

    f.close()

    return line

def deleteVerts(bmMesh, vertsIndex):
    
    verts = [0] * len(vertsIndex)
    count = 0

    bmMesh.verts.ensure_lookup_table() # Must be called each time a vertex is changed or deleted (Crashes otherwise)

    for v in vertsIndex: # Get list of verts to delete (must call above line if you need to look up vertex after deleting) 

        verts[count] = bmMesh.verts[int(v)]   
        count += 1 

    for v in verts: 
        bmMesh.verts.remove(v)
    
def createVertexMaterial(matName): # Creates a new material and then refreshes (creates) nodes

    mat = bpy.data.materials.new(name = matName)

    refreshAdvancedVertexMaterial(mat)

    return mat

def refreshBasicVertexMaterial(mat): # Plugs vertex colour directly into diffuse shader (NOT USED)

    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    links.clear()
    nodes.clear()

    vertexColour = nodes.new(type = "ShaderNodeVertexColor")    

    diffuse = nodes.new(type = "ShaderNodeBsdfDiffuse")
    output = nodes.new( type = "ShaderNodeOutputMaterial")

    links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])
    links.new(vertexColour.outputs["Color"], diffuse.inputs["Color"])

def createBasicColourRamp(nodes, interpolation, posZero, colZero, posOne, colOne): # Creates and returns a basic 2 node colour ramp for shaders

    baseColourRamp = nodes.new(type = "ShaderNodeValToRGB")
    baseColourRamp.color_ramp.interpolation = interpolation
    baseColourRamp.color_ramp.elements[0].position = posZero
    baseColourRamp.color_ramp.elements[0].color = colZero
    baseColourRamp.color_ramp.elements[1].position = posOne
    baseColourRamp.color_ramp.elements[1].color = colOne

    return baseColourRamp

def createMixRGBNode(nodes, blendType, factor): # Creates and returns a basic mix rgb for shader

    baseMix = nodes.new(type = "ShaderNodeMixRGB")
    baseMix.blend_type = blendType
    baseMix.inputs[0].default_value = factor
    return baseMix

def refreshAdvancedVertexMaterial(mat): # Creates and links necessary nodes for advanced skin shader (Values gained through trial and error in shader editor)

    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    links.clear()
    nodes.clear()

    output = nodes.new( type = "ShaderNodeOutputMaterial")
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")

    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    vertexColour = nodes.new(type = "ShaderNodeVertexColor")

    ################################### CREATE/LINK BASE COLOUR SHADERS ##########################################    

    #baseVoronoi = nodes.new(type = "ShaderNodeTexVoronoi")
    #baseVoronoi.inputs['Scale'].default_value = 305.6

    #baseColourRamp = createBasicColourRamp(nodes, 'B_SPLINE', 0.259, (0.767412,0.767412,0.767412,1), 0.814, (1,1,1,1))
    #baseMix = createMixRGBNode(nodes, 'MULTIPLY', 0.458)

    #links.new(baseVoronoi.outputs['Distance'], baseColourRamp.inputs['Fac'])
    #links.new(baseColourRamp.outputs['Color'], baseMix.inputs['Color2'])
    #links.new(vertexColour.outputs['Color'], baseMix.inputs['Color1'])
    #links.new(baseMix.outputs['Color'], bsdf.inputs['Base Color'])

    links.new(vertexColour.outputs['Color'], bsdf.inputs['Base Color'])

    ################################### CREATE/LINK SUBSURFACE SHADERS ########################################## 


    #sufNoise = nodes.new(type="ShaderNodeTexNoise")
    #sufNoise.inputs['Scale'].default_value = 40.0

    #sufColourRamp = createBasicColourRamp(nodes, 'LINEAR', 0.0, (0,0,0,1), 1.0, (1,1,1,1))
    #sufMix = createMixRGBNode(nodes, 'MULTIPLY', 1.0)

    #links.new(sufNoise.outputs['Color'], sufColourRamp.inputs['Fac'])
    #links.new(vertexColour.outputs['Color'], sufMix.inputs['Color2'])
    #links.new(sufColourRamp.outputs['Color'], sufMix.inputs['Color1'])
    #links.new(sufMix.outputs['Color'], bsdf.inputs['Subsurface Radius'])
    #links.new(sufMix.outputs['Color'], bsdf.inputs['Subsurface Color'])

    sufRgb = nodes.new(type="ShaderNodeRGB")
    sufRgb.outputs[0].default_value = (0.5, 0.0596146, 0.0151204, 1)

    links.new(vertexColour.outputs['Color'], bsdf.inputs['Subsurface Color'])

    links.new(sufRgb.outputs['Color'], bsdf.inputs['Subsurface Radius'])

    ################################### CREATE/LINK ROUGHNESS SHADERS ##########################################

    roughNoise = nodes.new(type="ShaderNodeTexNoise")
    roughNoise.inputs['Scale'].default_value = 15.1

    roughVoronoi = nodes.new(type = "ShaderNodeTexVoronoi")
    roughVoronoi.inputs['Scale'].default_value = 305.6

    roughNRamp = createBasicColourRamp(nodes, 'B_SPLINE' , 0.168, (0.447988,0.447988,0.447988,1), 0.886, (1,1,1,1))
    roughVRamp = createBasicColourRamp(nodes, 'LINEAR' , 0.0, (0.0412789,0.0412789,0.0412789,1), 1.0, (0.380056,0.380056,0.380056,1))
    roughMix = createMixRGBNode(nodes, 'MULTIPLY', 0.4)

    links.new(roughNoise.outputs['Fac'], roughNRamp.inputs['Fac'])
    links.new(roughNRamp.outputs['Color'], roughMix.inputs['Color1'])
    links.new(roughVoronoi.outputs['Distance'], roughVRamp.inputs['Fac'])
    links.new(roughVRamp.outputs['Color'], roughMix.inputs['Color2'])
    links.new(roughMix.outputs['Color'], bsdf.inputs['Roughness'])

    ################################### CREATE/LINK BUMP SHADERS ##########################################

    bumpVoronoi = nodes.new(type = "ShaderNodeTexVoronoi")
    bumpVoronoi.inputs['Scale'].default_value = 517.4

    bumpRamp = createBasicColourRamp(nodes, 'LINEAR' , 0.0, (0,0,0,1), 1, (0.0508648,0.0508648,0.0508648,1))


    bumpMap = nodes.new(type = "ShaderNodeBump")
    bumpMap.inputs['Strength'].default_value = 0.4
    bumpMap.inputs['Distance'].default_value = 0.1

    links.new(bumpVoronoi.outputs['Distance'], bumpRamp.inputs['Fac'])
    links.new(bumpRamp.outputs['Color'], bumpMap.inputs['Height'])
    links.new(bumpMap.outputs['Normal'], bsdf.inputs['Normal'])
    

    ######################################### EDIT OTHER VALUES ################################################

    bsdf.inputs['Subsurface'].default_value = 0.3
    bsdf.inputs['Metallic'].default_value = 0.0
    bsdf.inputs['Specular'].default_value = 0.1
    bsdf.inputs['Specular Tint'].default_value = 0.0
    bsdf.inputs['Anisotropic'].default_value = 0.0
    bsdf.inputs['Anisotropic Rotation'].default_value = 0.0
    bsdf.inputs['Sheen'].default_value = 0.0
    bsdf.inputs['Sheen Tint'].default_value = 0.345
    bsdf.inputs['Clearcoat'].default_value = 0.0
    bsdf.inputs['Clearcoat Roughness'].default_value = 0.03
    bsdf.inputs['IOR'].default_value = 1.450
    bsdf.inputs['Transmission'].default_value = 0.0
    bsdf.inputs['Transmission Roughness'].default_value = 0.0

def setMaterial(obj): # Create material for obj

    mat = bpy.data.materials.get("VertexColourMat") # Check to see if material exists in the scene

    if(mat is None): # If mat doesn't exist create it 
        mat = createVertexMaterial("VertexColourMat")
    
    if(not obj.data.materials): # If material not assigned to obj, assign it 
        obj.data.materials.append(mat)
        

    return

def smoothObject(mesh, shouldSmooth):
    for f in mesh.polygons:
        f.use_smooth = shouldSmooth          
    return

def changedSmooth(self, context): # Called when bool (Smooth) in pannel changes
    obj = bpy.context.object
    mesh = obj.data
    smoothObject(mesh, obj.my_settings.SmoothShader)
    pass

def refreshModel(sliderObj): # Refresh the model using the slider data

    obj = bpy.context.object

    scene = bpy.context.scene

    if(obj.my_settings.IsReseting): return # Stopes code being called every slider when group reseting (Blender is not thread safe)

    shouldSmooth = obj.my_settings.SmoothShader

    coofficient = getCoefficients(obj) # Grab the coefficients in list form

    if not(coofficient) : return # If there are no coefficients stop
    
    mesh = obj.data

    if not(aShapeKeeper.base): return # Not sure if this is ever called, it's here just in case
    
    filePath = obj.my_settings.FilePath
    blendshapePath = obj.my_settings.BlendshapePath

    if(filePath == "" and blendshapePath == ""):
        loadFaceModel(scene.global_setting.GlobalFilePath, scene.global_setting.GlobalBlendshapePath) # Load using the global settings if new model created
    else:

        if((filePath != aShapeKeeper.modelPath or blendshapePath != aShapeKeeper.blendShapePath) and aShapeKeeper.base != ""): #If model in shape keep object is not the same
            
            loadFaceModel(filePath, blendshapePath)
            
            if(obj.my_settings.HasEye): # Store current eyes in shape keep object
                children = getChildren(obj)
                if(len(children == 2)):
                    aShapeKeeper.leftEye = children[0]
                    aShapeKeeper.rightEye = children[1]

    morphModel = aShapeKeeper.base.draw_sample(coofficient[0],coofficient[2],coofficient[1])

    if((sliderObj.sliderType == SliderType.Colour.value or not mesh.vertex_colors) and obj.my_settings.ColourCount != 0 and not obj.my_settings.DeleteVertex): # If only colours are changing
        refreshColoursBM(mesh, morphModel.tci, morphModel.colors,shouldSmooth, False)

    else: # If any vertex positions are changing

        mesh.clear_geometry()

        verts = morphModel.vertices
        edges = []
        faces = morphModel.tvi

        mesh.from_pydata(verts, edges, faces) # Creates new mesh under the same object
        
        if(obj.my_settings.ColourCount == 0) :  # This is also called in refresh colours (Faster if called in refresh so redundant code is needed)
            smoothObject(mesh, shouldSmooth)

            if(obj.my_settings.DeleteVertex):

                deletionVerts = getdeletionVerts()    

                if(not deletionVerts == None):
                    bm = bmesh.new()
                    bm.from_mesh(mesh)

                    deleteVerts(bm, deletionVerts)

                    bm.to_mesh(mesh)

        else:
            refreshColoursBM(mesh, morphModel.tci, morphModel.colors,shouldSmooth, obj.my_settings.DeleteVertex)

    # If the model has left and right eye coordinets move and scale eyes
    if(obj.my_settings.HasEye and aShapeKeeper.leftEye != "" and aShapeKeeper.rightEye != "" and obj.my_settings.LeftEyeVertices != "" and obj.my_settings.RightEyeVertices != ""):

        leftVertex = obj.my_settings.LeftEyeVertices.split(",")

        if(int(leftVertex[0]) > len(obj.data.vertices)) : return
        if(int(leftVertex[1]) > len(obj.data.vertices)) : return

        handleEye(obj, int(leftVertex[0]), int(leftVertex[1]), aShapeKeeper.leftEye, obj.my_settings.EyeScaleOffset, obj.my_settings.LeftEyePosOffset)

        rightVertex = obj.my_settings.RightEyeVertices.split(",")

        if(int(rightVertex[0]) > len(obj.data.vertices)) : return
        if(int(rightVertex[1]) > len(obj.data.vertices)) : return

        handleEye(obj, int(rightVertex[0]), int(rightVertex[1]), aShapeKeeper.rightEye, obj.my_settings.EyeScaleOffset, obj.my_settings.RightEyePosOffset)

        aShapeKeeper.rightEye.scale = aShapeKeeper.leftEye.scale # If the user doesn't pick mirrored vertices just use left eye for both scales

        if(not obj.my_settings.DeleteVertex): # Breaks if deleted vertex comes back so the eyes are hidden
            aShapeKeeper.leftEye.hide_set(True)
            aShapeKeeper.rightEye.hide_set(True)
        else:
            aShapeKeeper.leftEye.hide_set(obj.my_settings.HideEyes)
            aShapeKeeper.rightEye.hide_set(obj.my_settings.HideEyes)

def handleEye(obj, leftVertex, rightVertex, eye, scaleOffset, posOffset): # Move and scale eye

    leftVec = mathutils.Vector(obj.data.vertices[leftVertex].co)
    rightVec = mathutils.Vector(obj.data.vertices[rightVertex].co)

    scale = abs((leftVec - rightVec).length) * scaleOffset

    eye.scale = (scale, scale, scale)

    newpos = (leftVec + rightVec) / 2

    eye.location = (newpos[0] * posOffset[0], newpos[1] * posOffset[1], newpos[2] * posOffset[2])

def resize(self, context): # if any of the shape, colour, expression sliders are changed refresh the model
    refreshModel(self)
    return

def createBlenderMesh(mesh): # Create a blender mesh using eos mesh model data

    blendObj = bpy.data.meshes.new("Morphable Object")  # add the new mesh    
    obj = bpy.data.objects.new(blendObj.name, blendObj)
    col = bpy.data.collections.get("Collection")
    col.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    verts = mesh.vertices
    edges = []
    faces = mesh.tvi

    blendObj.from_pydata(verts, edges, faces)

    return obj

def loadFaceModel(modelPath, blendshapePath = ""): # Load model into shape keeper

    morphablemodel_with_expressions = ""

    model = eos.morphablemodel.load_model(modelPath)

    modelType = model.get_expression_model_type()

    if(modelType == model.ExpressionModelType(0) and blendshapePath != ""):

        blendshapes = eos.morphablemodel.load_blendshapes(blendshapePath)
        
        morphablemodel_with_expressions = eos.morphablemodel.MorphableModel(model.get_shape_model(), blendshapes,
                                                                        color_model=eos.morphablemodel.PcaModel(),
                                                                        vertex_definitions=None,
                                                                        texture_coordinates=model.get_texture_coordinates())

    aShapeKeeper.base = model

    aShapeKeeper.modelPath = modelPath
    aShapeKeeper.blendShapePath = blendshapePath

    if(morphablemodel_with_expressions != ""):
        aShapeKeeper.base = morphablemodel_with_expressions
    else:
       return model

    return morphablemodel_with_expressions

def createBaseShape(FilePath, blendShapePath = ""): # Create the base morphable model, assign sliders to model
    
    base = loadFaceModel(FilePath, blendShapePath)

    secondMesh = base.draw_sample([0,0,0],[0,0,0]) # Draw the basic model

    obj = createBlenderMesh(secondMesh)

    modelType = base.get_expression_model_type()

    if(modelType == base.ExpressionModelType(0)): # If no model type
        obj.my_settings.ExpressionCount = 0
        obj.my_settings.ShapeCount = 0
        obj.my_settings.ColourCount = 0

    elif(modelType == base.ExpressionModelType.Blendshapes): # If blenshape model type
        obj.my_settings.ExpressionCount = len(base.get_expression_model())
        obj.my_settings.ShapeCount = base.get_shape_model().get_num_principal_components()
        obj.my_settings.ColourCount = base.get_color_model().get_num_principal_components()

    else: # If pca model type 
        obj.my_settings.ExpressionCount = base.get_expression_model().get_num_principal_components() 
        obj.my_settings.ShapeCount = base.get_shape_model().get_num_principal_components()
        obj.my_settings.ColourCount = base.get_color_model().get_num_principal_components()

    if(obj.my_settings.ColourCount != 0): setMaterial(obj) # If the model has a colour model set its material to advaced skin material 

    if not obj.get('_RNA_UI'): # Not sure but it's needed otherwise you can't add dynamic properties to model
        obj['_RNA_UI'] = {}

    for x in range(0,obj.my_settings.ShapeCount + obj.my_settings.ColourCount + obj.my_settings.ExpressionCount): # Create sliders (SliderProp List) and assign slider types to each
        prop = obj.sliders.sliderList.add()
        prop.value = 0

        if(x < obj.my_settings.ShapeCount) : 
            prop.sliderType = SliderType.Shape.value
            continue

        if(x < obj.my_settings.ColourCount + obj.my_settings.ShapeCount ) :
            prop.sliderType = SliderType.Colour.value
            continue

        prop.sliderType = SliderType.Expression.value

    return base

def getLabelText(showMore, sliderCount): # Formats the correct label for hiding and showing slider

    if(sliderCount < maxSlider): return ""
    
    if(showMore): return "Hide More Sliders (" + str(sliderCount) + " / " + str(sliderCount) + ")"

    return "Show Extra Sliders (" + str(maxSlider) + " / " + str(sliderCount) + ")"

def dirtyRefresh(self, context): # If the data is dirty (Changed without update) refresh the model
    obj = bpy.context.object
    obj.sliders.sliderList[0].value = obj.sliders.sliderList[0].value

def changedHideEyes(self, context): # If bool hide eyes had changed
    obj = context.object
    
    aShapeKeeper.leftEye.hide_set(obj.my_settings.HideEyes)
    aShapeKeeper.rightEye.hide_set(obj.my_settings.HideEyes)

def getEyeModel(filepath, objName, link): # Load and create the eye model

    with bpy.data.libraries.load(filepath, link=link) as (data_from, data_to):
                data_to.objects = [name for name in data_from.objects if name.startswith(objName)]

    #link object to current scene
    for obj in data_to.objects:
        if obj is not None:            
            bpy.context.collection.objects.link(obj)
            return obj

class MySettings(bpy.types.PropertyGroup): # All the data stored on every created object
   
    ExpressionCount : bpy.props.IntProperty(name = "ExpressionCount", description = "Number of Expressions",default = 0)
    ColourCount : bpy.props.IntProperty(name = "ColourCount", description = "Number of Colour",default = 0) 
    ShapeCount : bpy.props.IntProperty(name = "ShapeCount", description = "Number of Shapes",default = 0)   

    ColourShowMore : bpy.props.BoolProperty(name = "ColourShowMore", description = "Should I show more", default = False)
    ShapeShowMore : bpy.props.BoolProperty(name = "ShapeShowMore", description = "Should I show more", default = False)
    ExpressionShowMore : bpy.props.BoolProperty(name = "ExpressionShowMore", description = "Should I show more", default = False)

    SmoothShader : bpy.props.BoolProperty(name = "Smooth Shading", description  = "Should I smooth shade", default = False, update = changedSmooth)
    IsReseting : bpy.props.BoolProperty(name = "Reseting Slidser", default = False)

    FilePath : bpy.props.StringProperty(name = "File Path:", subtype = "FILE_PATH")
    BlendshapePath : bpy.props.StringProperty(name = "Blendshape Path:", subtype = "FILE_PATH")

    FileName : bpy.props.StringProperty(name = "File")

    VertexFileName : bpy.props.StringProperty(name = "File Name")
    VertexOverwrite : bpy.props.BoolProperty(name = "Overwrite Vertex File", default = False)

    DeleteVertex : bpy.props.BoolProperty(name = "Hide Vertex", description  = "Should I delete vertex in file", default = False, update = dirtyRefresh)

    ShapeSD : bpy.props.FloatProperty(name = "Shape SD",min = 0, max = 2, description = "Standard Deviation for Shape", default = 0)
    ColourSD : bpy.props.FloatProperty(name = "Colour SD",min = 0, max = 2, description = "Standard Deviation for Colour", default = 0)
    ExpreSD : bpy.props.FloatProperty(name = "Expre SD",min = 0, max = 2, description = "Standard Deviation for Expressions", default = 0)

    HasEye : bpy.props.BoolProperty(name = "Has Eye", default = False)
    LeftEyeVertices : bpy.props.StringProperty(name = "Vertex",default = "")
    RightEyeVertices : bpy.props.StringProperty(name = "Vertex",default = "")

    HideEyes : bpy.props.BoolProperty(name = "Hide Eyes", description  = "Should I Hide eyes", default = False, update = changedHideEyes)

    EyeScaleOffset : bpy.props.FloatProperty(name = "Eye Scale Offset", description = "Offset for the eye scale", default = 1, update = dirtyRefresh)

    LeftEyePosOffset : bpy.props.FloatVectorProperty(name = "Pos offset", description = "Offset for left eye position", default = (1,1,1), update = dirtyRefresh)
    RightEyePosOffset : bpy.props.FloatVectorProperty(name = "Pos offset", description = "Offset for right eye position", default = (1,1,1), update = dirtyRefresh)

class GlobalSettings(bpy.types.PropertyGroup): # All the data stored in the scene
    GlobalFilePath : bpy.props.StringProperty(subtype = "FILE_PATH")
    GlobalBlendshapePath : bpy.props.StringProperty(name = "Blendshape Path:", subtype = "FILE_PATH")
    GlobalVertexStore : bpy.props.StringProperty(subtype = "FILE_PATH")
    GlobalEyePath : bpy.props.StringProperty(subtype = "FILE_PATH")

class SliderProp(bpy.types.PropertyGroup): # The data in a slider property

    value : bpy.props.FloatProperty(name = "Length",min = -3, max = 3, description = "DataLength", default = 0, update = resize, options = {'ANIMATABLE'})
    sliderType : bpy.props.IntProperty(name = "SliderType", description = "Int enum value for the slider type", default = 0)

class SliderList(bpy.types.PropertyGroup): # The list of sliders
    sliderList : bpy.props.CollectionProperty(type=SliderProp)

class Create_New_Model(bpy.types.Operator): # Create model button
    bl_idname = "view3d.create_new_model"
    bl_label = "Create New Model"
    bl_destription = "A button to create a new morphable face"

    def execute(self, context): # Create model button pressed 

        scene = context.scene

        if(scene.global_setting.GlobalFilePath[-3:] != "bin") : # If file is not compatible 
            self.report({"ERROR"}, "File not compatible")
            scene.global_setting.GlobalFilePath = ""
            return {'FINISHED'}

        blendshapePath = scene.global_setting.GlobalBlendshapePath

        if(blendshapePath[-3:] != "bin" and not blendshapePath == "") :  # If file is not compatible 
            self.report({"ERROR"}, "File not compatible")
            scene.global_setting.GlobalBlendshapePath = ""
            return {'FINISHED'}


        createBaseShape(scene.global_setting.GlobalFilePath, blendshapePath)
        obj = context.object

        obj.my_settings.FilePath = scene.global_setting.GlobalFilePath # Add un-editable to pannel for user debugging 
        obj.my_settings.FileName = (scene.global_setting.GlobalFilePath.split("\\")[-1])[:-4]

        obj.my_settings.BlendshapePath = blendshapePath

        obj.scale = (0.03, 0.03, 0.03) # The head is huge on import

        return {'FINISHED'}

class Save_Selected_Vertex(bpy.types.Operator): # Save selected vertices button
    bl_idname = "view3d.save_selected_vertex"
    bl_label = "Save Selected Vertices"
    bl_destription = "A button to save selected vertices"

    def execute(self, context): # Button pressed

        scene = context.scene   

        obj = bpy.context.object

        mesh =  obj.data

        selectedVerts = [v for v in mesh.vertices if v.select] # Loop through all vertices and collect selected vertices

        if(scene.global_setting.GlobalVertexStore[-1:] != "\\" and scene.global_setting.GlobalVertexStore[-1:] != "/") : # Must be a folder path
            self.report({"ERROR"}, "File not compatible")
            scene.global_setting.GlobalVertexStore = ""
            return {'FINISHED'}   

        fileNumber = -1
        fileName = obj.my_settings.VertexFileName
        filePath = scene.global_setting.GlobalVertexStore  

        if(fileName == ""): # If file name empty use this instead
            fileName = "VertexIndices"

        if(fileName[-4:] == ".txt"): # Remove .txt if it's there
            fileName = fileName[:-4]

        shortPath = fileName # Filename gets changed so this is the original

        if (not obj.my_settings.VertexOverwrite): # If user wants a unique name and the previous name not overwritten add _x

            if(len(shortPath) > 2):
                if(shortPath[-2] == "_"):
                    shortPath = shortPath[:-2]

            while (os.path.isfile(filePath + fileName + ".txt")):

                fileNumber += 1
                fileName = shortPath + "_" + str(fileNumber) 

        fileName += ".txt"

        obj.my_settings.VertexFileName = fileName

        f = open(filePath + fileName, "w")

        first = True

        for v in selectedVerts: # Write data as x,y,z using the index of the vertex
            if(first):
                f.write(str(v.index))
                first = False
            else:
                f.write("," + str(v.index))

        f.close()

        obj.sliders.sliderList[0].value = obj.sliders.sliderList[0].value # Refresh model
        
        return {'FINISHED'}

class Create_Copy_Model(bpy.types.Operator): # Create a copy of selected model button
    bl_idname = "view3d.create_copy_model"
    bl_label = "Create Copy Model"
    bl_destription = "A button to create a new morphable face"

    def execute(self, context):

        obj = context.object

        filePath = obj.my_settings.FilePath
        blendshapePath = obj.my_settings.BlendshapePath

        createBaseShape(filePath, blendshapePath)

        obj = context.object #Grab the new object

        obj.my_settings.FilePath = filePath
        obj.my_settings.FileName = (filePath.split("\\")[-1])[:-4]

        obj.my_settings.BlendshapePath = blendshapePath
        obj.scale = (0.03, 0.03, 0.03) # Object huge on import
        

        return {'FINISHED'}

class Link_Eye_Model(bpy.types.Operator): # Link eyes button
    bl_idname = "view3d.link_eye_model"
    bl_label = "Create Eye Model"
    bl_destription = "A button to create a new eye model"

    def execute(self, context):

        head = context.object

        scene = context.scene   

        filepath = scene.global_setting.GlobalEyePath

        if(filepath[-5:] != "blend") : # If file is not compatible 
            self.report({"ERROR"}, "File not compatible")
            scene.global_setting.GlobalEyePath = ""
            return {'FINISHED'}

        leftEye = getEyeModel(filepath, "Eye", False)
        rightEye = getEyeModel(filepath, "Eye", False)

        leftEye.parent = head # Parent both eyes
        rightEye.parent = head

        leftEye.scale = (11.6496,11.6496,11.6496) # These is a guess to get the eye visible to the user
        rightEye.scale = (11.6496,11.6496,11.6496)

        leftEye.location = (-30.9127, 24.1305, 72.3501)
        leftEye.rotation_euler = (-1.57,0,0)

        rightEye.location = (30.9127, 24.1305, 72.3501)
        rightEye.rotation_euler = (-1.57,0,0)

        head.my_settings.HasEye = True

        aShapeKeeper.leftEye = leftEye
        aShapeKeeper.rightEye = rightEye

        return {'FINISHED'}

class Link_LEye_Vertex(bpy.types.Operator): # Link left eye vetices button
    bl_idname = "view3d.link_leye_vertex"
    bl_label = "Link Left Eye Vertices"
    bl_destription = "A button to link two verticies for the eye"

    def execute(self, context):        
        
        head = context.object  
        
        children = getChildren(head);     

        if(children == []):
            self.report({"ERROR"}, "No eyes imported")
            return {'FINISHED'}


        if(not len(children) == 2):
            self.report({"ERROR"}, "Too many eyes")
            return {'FINISHED'}
      
        leftEye = children[0]   

        mesh =  head.data

        selectedVerts = [v for v in mesh.vertices if v.select] # Loop through vertices and collect selected vertices

        if(not len(selectedVerts) == 2):
            self.report({"ERROR"}, "2 Verts haven't been selected")
            return {'FINISHED'}

        head.my_settings.LeftEyeVertices = str(selectedVerts[0].index) + "," + str(selectedVerts[1].index) # Blender doens't store lists so keep it as a string 

        if(aShapeKeeper.leftEye != "" and aShapeKeeper.rightEye != ""): # Only refresh if both left and right eye have been set
            head.sliders.sliderList[0].value = head.sliders.sliderList[0].value

        return {'FINISHED'}

class Link_REye_Vertex(bpy.types.Operator):# Link right eye vetices button
    bl_idname = "view3d.link_reye_vertex"
    bl_label = "Link Right Eye Vertices"
    bl_destription = "A button to link two verticies for the eye"

    def execute(self, context):        
        
        head = context.object  
        
        children = getChildren(head);     

        if(children == []):
            self.report({"ERROR"}, "No eyes imported")
            return {'FINISHED'}


        if(not len(children) == 2):
            self.report({"ERROR"}, "Too many eyes")
            return {'FINISHED'}
      
        rightEye = children[1]   

        mesh =  head.data

        selectedVerts = [v for v in mesh.vertices if v.select] # Loop through vertices and collect selected vertices

        if(not len(selectedVerts) == 2):
            self.report({"ERROR"}, "2 Verts haven't been selected")
            return {'FINISHED'}

        head.my_settings.RightEyeVertices = str(selectedVerts[0].index) + "," + str(selectedVerts[1].index) # Blender doens't store lists so keep it as a string

        if(aShapeKeeper.leftEye != "" and aShapeKeeper.rightEye != ""): # Only refresh if both left and right eye have been set
            head.sliders.sliderList[0].value = head.sliders.sliderList[0].value

        return {'FINISHED'}

class Show_More_Colour(bpy.types.Operator): # Show more colour sliders button
    bl_idname = "view3d.show_more_colour"
    bl_label = "Show more colour sliders"
    bl_destription = "A button to show more colour sliders"

    def execute(self, context):

        obj = context.object

        obj.my_settings.ColourShowMore = not obj.my_settings.ColourShowMore

        return {'FINISHED'}
        
class Show_More_Shape(bpy.types.Operator): # show more shape sliders button
    bl_idname = "view3d.show_more_shape"
    bl_label = "Show more shape sliders"
    bl_destription = "A button to show more shape sliders"

    def execute(self, context):

        obj = context.object

        obj.my_settings.ShapeShowMore = not obj.my_settings.ShapeShowMore

        return {'FINISHED'}

class Show_More_Expression(bpy.types.Operator): # show more expression sliders button
    bl_idname = "view3d.show_more_expression"
    bl_label = "Show more expression sliders"
    bl_destription = "A button to show more expression sliders"

    def execute(self, context):

        obj = context.object

        obj.my_settings.ExpressionShowMore = not obj.my_settings.ExpressionShowMore

        return {'FINISHED'}

class Reset_Sliders(bpy.types.Operator): # Resets all sliders to zero
    bl_idname = "view3d.reset_sliders"
    bl_label = "Resets all the sliders to zero"
    bl_destription = "A button to reset all the sliders"

    def execute(self, context):

        obj = context.object
        obj.my_settings.IsReseting = True # Stop the update being called during change

        for x in range(0, obj.my_settings.ShapeCount + obj.my_settings.ExpressionCount + obj.my_settings.ColourCount): 

            obj.sliders.sliderList[x].value = 0.0

        obj.my_settings.IsReseting = False

        obj.sliders.sliderList[0].value = 0.0 #Trigger the refresh

        return {'FINISHED'}

class Random_Sliders(bpy.types.Operator): # Randomise the sliders
    bl_idname = "view3d.random_sliders"
    bl_label = "Randomizes all the sliders"
    bl_destription = "A button to radomize all the sliders"

    def execute(self, context):

        obj = context.object
        obj.my_settings.IsReseting = True # Stop the update being called during change
        

        ############################ Normal (Gaussian) Random ##################################################

        normalListShape = random.normal(loc = 0, scale = obj.my_settings.ShapeSD, size = obj.my_settings.ShapeCount) # Create gaussian random lists using values inputed by user
        normalListColour = random.normal(loc = 0, scale = obj.my_settings.ColourSD, size = obj.my_settings.ColourCount)
        normalListExp = random.normal(loc = 0, scale = obj.my_settings.ExpreSD, size = obj.my_settings.ExpressionCount)

        for x in range(0, obj.my_settings.ShapeCount + obj.my_settings.ExpressionCount + obj.my_settings.ColourCount):             

            if x < obj.my_settings.ShapeCount:
                
                obj.sliders.sliderList[x].value = normalListShape[x]

            elif x < obj.my_settings.ShapeCount + obj.my_settings.ColourCount:
                obj.sliders.sliderList[x].value = normalListColour[x - obj.my_settings.ShapeCount]

            else:
                obj.sliders.sliderList[x].value = normalListExp[x - obj.my_settings.ShapeCount - obj.my_settings.ColourCount]


        ##########################################################################################################

        obj.my_settings.IsReseting = False

        obj.sliders.sliderList[0].value = obj.sliders.sliderList[0].value #Trigger the refresh

        return {'FINISHED'}

class Main_PT_Panel(bpy.types.Panel): # The main pannel
    bl_idname = "MORPH_PT_Panel"
    bl_label = "Morph Panel"
    bl_category = "Morph Addon"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object

        box = layout.box() # Creates a new section in the pannel
        
        isInObjectMode = True

        if(obj != None ):
            isInObjectMode = obj.mode == "OBJECT" 

        row = box.row()
        row.operator('view3d.create_new_model')  
        row.enabled = isInObjectMode 

        row = box.row()
        row.prop(scene.global_setting, "GlobalFilePath", text = "Model Path")
        row.enabled = isInObjectMode 

        row = box.row()
        row.prop(scene.global_setting, "GlobalBlendshapePath", text = "Blendshape Path")
        row.enabled = isInObjectMode        

        if(obj != None):

            objType = getattr(obj, "type", "")

            if(objType == "MESH"):                             

                box = layout.box() 

                row = box.row()
                row.label(text = "Object: " + obj.name)
                row.enabled = isInObjectMode  

                shapeCount = obj.my_settings.ShapeCount
                colourCount = obj.my_settings.ColourCount
                expressionCount = obj.my_settings.ExpressionCount   

                row = box.row()
                row.prop(obj.my_settings, "SmoothShader")
                row.enabled = isInObjectMode     

                if(shapeCount > 0 or colourCount > 0 or expressionCount > 0): # If the object is a morphable head

                    box = layout.box()  

                    row = box.row()
                    row.operator('view3d.create_copy_model')  
                    row.enabled = isInObjectMode

                    row = box.row()
                    row.prop(obj.my_settings, "FileName")
                    row.enabled = False # Disable editing

                    row = box.row()
                    row.prop(obj.my_settings, "FilePath")
                    row.enabled = False

                    row = box.row()
                    row.prop(obj.my_settings, "BlendshapePath")
                    row.enabled = False

                    box = layout.box()  

                    row = box.row()
                    row.operator('view3d.save_selected_vertex')  
                    row.enabled = isInObjectMode 

                    row = box.row()
                    row.prop(scene.global_setting, "GlobalVertexStore", text = "Folder")
                    row.enabled = isInObjectMode 

                    row = box.row()
                    row.prop(obj.my_settings, "VertexFileName")
                    row.enabled = isInObjectMode 

                    row = box.row()
                    row.prop(obj.my_settings, "VertexOverwrite")
                    row.enabled = isInObjectMode 

                    row = box.row()
                    row.prop(obj.my_settings, "DeleteVertex")
                    row.enabled = isInObjectMode     

                    box = layout.box() 
                    row = box.row()
                    row.operator('view3d.link_eye_model')  
                    row.enabled = isInObjectMode

                    row = box.row()
                    row.prop(scene.global_setting, "GlobalEyePath", text = "Eye Path")
                    row.enabled = isInObjectMode 

                    if(aShapeKeeper.leftEye != "" and aShapeKeeper.rightEye != ""): # Only show if both eyes exist
                        row = box.row()
                        row.prop(obj.my_settings, "HideEyes", text = "Hide Eyes")
                        row.enabled = isInObjectMode 

                    box = layout.box()  

                    row = box.row()
                    row.operator("view3d.link_leye_vertex")  
                    row.enabled = obj.my_settings.DeleteVertex and isInObjectMode

                    row = box.row()
                    row.prop(obj.my_settings, "LeftEyeVertices")
                    row.enabled = False 

                    row = box.row()
                    row.prop(obj.my_settings, "LeftEyePosOffset")
                    row.enabled = isInObjectMode   

                    box = layout.box()               

                    row = box.row()
                    row.operator("view3d.link_reye_vertex")  
                    row.enabled = obj.my_settings.DeleteVertex and isInObjectMode                                      

                    row = box.row()
                    row.prop(obj.my_settings, "RightEyeVertices")
                    row.enabled = False  

                    row = box.row()
                    row.prop(obj.my_settings, "RightEyePosOffset")
                    row.enabled = isInObjectMode        

                    box = layout.box()   

                    row = box.row()
                    row.prop(obj.my_settings, "EyeScaleOffset")
                    row.enabled = isInObjectMode      
                    
                    box = layout.box() 
                    
                    row = box.row()
                    row.operator('view3d.random_sliders')
                    row.enabled = isInObjectMode

                    row = box.row()
                    row.prop(obj.my_settings, "ShapeSD")
                    row.enabled = isInObjectMode

                    row = box.row()
                    row.prop(obj.my_settings, "ColourSD")
                    row.enabled = isInObjectMode

                    row = box.row()
                    row.prop(obj.my_settings, "ExpreSD")
                    row.enabled = isInObjectMode

                    box = layout.box() 

                    row = box.row()
                    row.operator('view3d.reset_sliders')
                    row.enabled = isInObjectMode   

                if(shapeCount > 0): # Handle Shape Sliders
                    box = layout.box() 
                    row = box.row()
                    row.label(text = "Shape: ")
                    row = box.row()           

                    labelText = getLabelText(obj.my_settings.ShapeShowMore, shapeCount)

                    showMoreCount = 0
                    if(obj.my_settings.ShapeShowMore): showMoreCount = shapeCount - maxSlider

                    if(labelText != ""):

                        row = box.row()
                        row.operator('view3d.show_more_shape', text = labelText)  
                        row.enabled = isInObjectMode
                        row = box.row()

                    
                    cf = row.grid_flow(row_major = True, columns = 3, align = False)        
                    row.enabled = isInObjectMode   

                    for x in range(0,shapeCount):  

                        if x > maxSlider + showMoreCount: break
                        k = "line_%d" % x   
                        cf.prop(obj.sliders.sliderList[x], "value", text = str(x)+ ":") # Get the correct slider

                if(colourCount > 0): # Handle Colour Sliders
                    box = layout.box() 
                    row = box.row()
                    row.label(text = "Colour: ")
                    row = box.row()

                    labelText = getLabelText(obj.my_settings.ColourShowMore, colourCount)

                    showMoreCount = 0
                    if(obj.my_settings.ColourShowMore): showMoreCount = colourCount + shapeCount - maxSlider

                    if(labelText != ""):

                        row = box.row()
                        row.operator('view3d.show_more_colour', text = labelText )  
                        row.enabled = isInObjectMode
                        row = box.row()

                    cf = row.grid_flow(row_major = True, columns = 3, align = False)    
                    row.enabled = isInObjectMode                 
                               
                    for x in range(shapeCount,shapeCount + colourCount): 

                        if(x - shapeCount) > maxSlider + showMoreCount : break
                        k = "line_%d" % x   
                        cf.prop(obj.sliders.sliderList[x], "value", text = str(x - shapeCount)+ ":")
                
                if(expressionCount > 0): # Handle Expression Sliders
                    box = layout.box() 
                    row = box.row()
                    row.label(text = "Expression: ")
                    row = box.row()

                    labelText = getLabelText(obj.my_settings.ExpressionShowMore, expressionCount)

                    if(labelText != ""):
                        row = box.row()
                        row.operator('view3d.show_more_expression', text = labelText)  
                        row.enabled = isInObjectMode
                        row = box.row()

                    cf = row.grid_flow(row_major = True, columns = 3, align = False)  
                    row.enabled = isInObjectMode

                    showMoreCount = 0

                    if(obj.my_settings.ExpressionShowMore): showMoreCount = shapeCount + colourCount + expressionCount - maxSlider

                    for x in range(shapeCount + colourCount, shapeCount + colourCount + expressionCount):   

                        if( x - shapeCount - colourCount > maxSlider + showMoreCount) : break
                        k = "line_%d" % x    
                        cf.prop(obj.sliders.sliderList[x], "value", text = str(x - shapeCount - colourCount) + ":") 

classes = (
    Main_PT_Panel,
    Create_New_Model,
    Create_Copy_Model,
    MySettings,
    SliderProp,
    SliderList,
    Show_More_Colour,
    Show_More_Shape,
    Show_More_Expression,
    Reset_Sliders,
    Random_Sliders,
    GlobalSettings,
    Save_Selected_Vertex,
    Link_Eye_Model,
    Link_LEye_Vertex,
    Link_REye_Vertex
        )

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)   

    bpy.types.Object.my_settings = bpy.props.PointerProperty(type=MySettings)
    bpy.types.Object.sliders = bpy.props.PointerProperty(type=SliderList)
    bpy.types.Scene.global_setting = bpy.props.PointerProperty(type=GlobalSettings)
    print("EOS Interface Loaded")

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)             

if __name__ == "__main__":
    try:
        unregister()
    except:
        pass
    register()