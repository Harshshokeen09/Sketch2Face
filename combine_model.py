import jittor as jt
from jittor import Module
from jittor import nn
import networks
from AE_model import AE_Model

#The Editing network
class Combine_Model(nn.Module):
    def name(self):
        return 'Combine_Model'
    
    def initialize(self):
        ##### define networks        
        # Generator network       

        #The axis of x,y; the size of each part
        self.part = {'bg': (0, 0, 512),
                     'eye1': (108, 156, 128),
                     'eye2': (255, 156, 128),
                     'nose': (182, 232, 160),
                     'mouth': (169, 301, 192)}

        self.Sketch_Encoder_Part = {}
        self.Gen_Part = {}
        self.Image_Encoder_Part = {}

        for key in self.part.keys():
            self.Sketch_Encoder_Part[key] = networks.GeometryEncoder(input_nc = 3, output_nc = 3, 
                                                                    ngf = 64, n_downsampling = 4, n_blocks = 1)
            self.Image_Encoder_Part[key] = networks.GeometryEncoder(input_nc = 3, output_nc = 3, 
                                                                    ngf = 64, n_downsampling = 4, n_blocks = 6)
            self.Gen_Part[key] = networks.Part_Generator(input_nc=3, output_nc=3, 
                                                                    ngf = 64, n_downsampling = 4, n_blocks = 4)
        
        self.netG = networks.GlobalGenerator(input_nc = 64, output_nc = 3, 
                                        ngf = 64, n_downsampling = 4, n_blocks = 4)
            
        for key in self.part.keys():
            print("load the weight of " + key)
            self.Sketch_Encoder_Part[key].load('./checkpoints/sketch_encoder/sketch_encoder_' + key + '.pkl')
            self.Image_Encoder_Part[key].load('./checkpoints/image_encoder/image_encoder_' + key + '.pkl')
            self.Gen_Part[key].load('./checkpoints/generator/generator_' + key + '.pkl')

        print("load the weight of global fuse")
        self.netG.load('./checkpoints/global_fuse.pkl')

    def inference(self, sketch, appear, geo_type):
        part_feature = {}
        for key in self.part.keys():
            sketch_part = sketch[:,:,self.part[key][1]: self.part[key][1] + self.part[key][2], self.part[key][0]: self.part[key][0] + self.part[key][2]]
            appear_part = appear[:,:,self.part[key][1]: self.part[key][1] + self.part[key][2], self.part[key][0]: self.part[key][0] + self.part[key][2]]
            with jt.no_grad():
                if geo_type == "sketch":
                    sketch_feature = self.Sketch_Encoder_Part[key](sketch_part)
                else:
                    sketch_feature = self.Image_Encoder_Part[key](sketch_part)
                part_feature[key] = self.Gen_Part[key].feature_execute(sketch_feature, appear_part)
        
        bg_r_feature = part_feature['bg']
        bg_r_feature[:, :, 301:301 + 192, 169:169 + 192] = part_feature['mouth']
        bg_r_feature[:, :, 232:232 + 160 - 36, 182:182 + 160] = part_feature['nose'][:, :, :-36, :]
        bg_r_feature[:, :, 156:156 + 128, 108:108 + 128] = part_feature['eye1']
        bg_r_feature[:, :, 156:156 + 128, 255:255 + 128] = part_feature['eye2']    
        
        with jt.no_grad():
            fake_image = self.netG(bg_r_feature)

        return fake_image

#The Projection network
class Combine_Model_Projection(nn.Module):
    def name(self):
        return 'Combine_Model_Projection'
    
    def initialize(self):
        ##### define networks        
        # Generator network       

        #The axis of x,y; the size of each part
        self.part = {'bg': (0, 0, 512),
                     'eye1': (108, 156, 128),
                     'eye2': (255, 156, 128),
                     'nose': (182, 232, 160),
                     'mouth': (169, 301, 192)}

        self.AE_Part = {}
        self.Sketch_Encoder_Part = {}
        self.Gen_Part = {}

        for key in self.part.keys():
            self.AE_Part[key] = AE_Model()
            self.Sketch_Encoder_Part[key] = networks.GeometryEncoder(input_nc=32, output_nc=3, 
                                                                    ngf=32, n_downsampling=4, n_blocks=0)
            self.Gen_Part[key] = networks.Part_Generator(input_nc=32, output_nc=3, 
                                                        ngf=32, n_downsampling=4, n_blocks=4, norm_layer='in')
        
        self.netG = networks.GlobalGenerator(input_nc=32, output_nc=3, ngf=32, n_downsampling=4, n_blocks=9, norm='bn')
            
        for key in self.part.keys():
            print("load the weight of " + key)
            self.Sketch_Encoder_Part[key].load('./checkpoints/Drawing/geo_encoder_' + key + '.pkl')
            self.Gen_Part[key].load('./checkpoints/Drawing/part_gen_' + key + '.pkl')
            self.AE_Part[key].initialize(key)

        print("load the weight of global fuse")
        self.netG.load('./checkpoints/Drawing/global_fuse.pkl')
        self.netG.eval()

    def inference(self, sketch, appear, gender, part_weights):
        #### generate images from hand-drawn sketches
        #sketch: hand-drawn sketch image  appear: appearance image
        #gender: 1, man     0, female
        #part_weights: dict, the weight of project vector for parts
        part_feature = {}
        for key in self.part.keys():
            sketch_part = sketch[:,:,self.part[key][1]: self.part[key][1] + self.part[key][2], self.part[key][0]: self.part[key][0] + self.part[key][2]]
            appear_part = appear[:,:,self.part[key][1]: self.part[key][1] + self.part[key][2], self.part[key][0]: self.part[key][0] + self.part[key][2]]
            with jt.no_grad():
                sketch_geo = self.AE_Part[key].inference(sketch_part, gender, part_weights[key])
                sketch_feature = self.Sketch_Encoder_Part[key](sketch_geo)
                part_feature[key] = self.Gen_Part[key].feature_execute(sketch_feature, appear_part)
        
        bg_r_feature = part_feature['bg']
        bg_r_feature[:, :, 301:301 + 192, 169:169 + 192] = part_feature['mouth']
        bg_r_feature[:, :, 232:232 + 160 - 36, 182:182 + 160] = part_feature['nose'][:, :, :-36, :]
        bg_r_feature[:, :, 156:156 + 128, 108:108 + 128] = part_feature['eye1']
        bg_r_feature[:, :, 156:156 + 128, 255:255 + 128] = part_feature['eye2']    
        
        with jt.no_grad():
            fake_image = self.netG(bg_r_feature)

        return fake_image

