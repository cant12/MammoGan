# Copyright 2019-2020 Stanislav Pidhorskyi
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import torch.utils.data
from torchvision.utils import save_image
import random
from net import *
from model import Model
from launcher import run
from checkpointer import Checkpointer
from dlutils.pytorch import count_parameters
from defaults import get_cfg_defaults
import lreq
import tqdm
from PIL import Image


lreq.use_implicit_lreq.set(True)

def place(canvas, image, x, y):
    im_size = image.shape[2]
    if len(image.shape) == 4:
        image = image[0]
    canvas[:, y: y + im_size, x: x + im_size] = image * 0.5 + 0.5


def save_sample(model, sample, i):
    os.makedirs('results', exist_ok=True)

    with torch.no_grad():
        model.eval()
        x_rec = model.generate(model.generator.layer_count - 1, 1, z=sample)

        def save_pic(x_rec):
            resultsample = x_rec * 0.5 + 0.5
            resultsample = resultsample.cpu()
            save_image(resultsample,
                       'sample_%i_lr.png' % i, nrow=16)

        save_pic(x_rec)


def sample(cfg, logger):
    torch.cuda.set_device(0)
    # print("hi")
    # cfg.OUTPUT_DIR = "mammogans_blur_result"
    # print(cfg.OUTPUT_DIR)
    model = Model(
        startf=cfg.MODEL.START_CHANNEL_COUNT,
        layer_count=cfg.MODEL.LAYER_COUNT,
        maxf=cfg.MODEL.MAX_CHANNEL_COUNT,
        latent_size=cfg.MODEL.LATENT_SPACE_SIZE,
        truncation_psi=cfg.MODEL.TRUNCATIOM_PSI,
        truncation_cutoff=cfg.MODEL.TRUNCATIOM_CUTOFF,
        mapping_layers=cfg.MODEL.MAPPING_LAYERS,
        channels=cfg.MODEL.CHANNELS,
        generator=cfg.MODEL.GENERATOR,
        encoder=cfg.MODEL.ENCODER)

    model.cuda(0)
    model.eval()
    model.requires_grad_(False)

    decoder = model.decoder
    encoder = model.encoder
    mapping_tl = model.mapping_tl
    mapping_fl = model.mapping_fl
    dlatent_avg = model.dlatent_avg

    logger.info("Trainable parameters generator:")
    count_parameters(decoder)

    logger.info("Trainable parameters discriminator:")
    count_parameters(encoder)

    arguments = dict()
    arguments["iteration"] = 0

    model_dict = {
        'discriminator_s': encoder,
        'generator_s': decoder,
        'mapping_tl_s': mapping_tl,
        'mapping_fl_s': mapping_fl,
        'dlatent_avg': dlatent_avg
    }

    checkpointer = Checkpointer(cfg,
                                model_dict,
                                {},
                                logger=logger,
                                save=False)

    extra_checkpoint_data = checkpointer.load()

    model.eval()

    print("hi")

    cfg.OUTPUT_DIR = "mammogans_blur_result"
    model1 = Model(
        startf=cfg.MODEL.START_CHANNEL_COUNT,
        layer_count=cfg.MODEL.LAYER_COUNT,
        maxf=cfg.MODEL.MAX_CHANNEL_COUNT,
        latent_size=cfg.MODEL.LATENT_SPACE_SIZE,
        truncation_psi=cfg.MODEL.TRUNCATIOM_PSI,
        truncation_cutoff=cfg.MODEL.TRUNCATIOM_CUTOFF,
        mapping_layers=cfg.MODEL.MAPPING_LAYERS,
        channels=cfg.MODEL.CHANNELS,
        generator=cfg.MODEL.GENERATOR,
        encoder=cfg.MODEL.ENCODER)
    
    model1.cuda(0)
    model1.eval()
    model1.requires_grad_(False)

    decoder1 = model1.decoder
    encoder1 = model1.encoder
    mapping_tl1 = model1.mapping_tl
    mapping_fl1 = model1.mapping_fl
    dlatent_avg1 = model1.dlatent_avg

    logger.info("Trainable parameters generator:")
    count_parameters(decoder1)

    logger.info("Trainable parameters discriminator:")
    count_parameters(encoder1)
    
    model_dict1 = {
        'discriminator_s': encoder1,
        'generator_s': decoder1,
        'mapping_tl_s': mapping_tl1,
        'mapping_fl_s': mapping_fl1,
        'dlatent_avg': dlatent_avg1
    }

    cfg.OUTPUT_DIR = "mammogans_blur_result"
    checkpointer1 = Checkpointer(cfg,
                                model_dict1,
                                {},
                                logger=logger,
                                save=False)

    extra_checkpoint_data1 = checkpointer1.load()

    model1.eval()

    layer_count = cfg.MODEL.LAYER_COUNT

    def encode(x,model):
        Z, _ = model.encode(x, layer_count - 1, 1)
        Z = Z.repeat(1, model.mapping_fl.num_layers, 1)
        return Z

    def decode(x,model):
        layer_idx = torch.arange(2 * cfg.MODEL.LAYER_COUNT)[np.newaxis, :, np.newaxis]
        ones = torch.ones(layer_idx.shape, dtype=torch.float32)
        coefs = torch.where(layer_idx < model.truncation_cutoff, ones, ones)
        # x = torch.lerp(model.dlatent_avg.buff.data, x, coefs)
        return model.decoder(x, layer_count - 1, 1, noise=True)

    path = cfg.DATASET.SAMPLES_PATH
    im_size = 2 ** (cfg.MODEL.LAYER_COUNT + 1)

    paths = list(os.listdir(path))

    paths = sorted(paths)
    random.seed(1)
    random.shuffle(paths)

    def make(paths):
        canvas = []
        with torch.no_grad():
            for filename in paths:
                img = np.asarray(Image.open(path + '/' + filename))
                if(img.shape==(28,28)):
                    img = np.pad(img,(2,2))
                    img = np.array([img,img,img]).transpose((1,2,0))
                flag = False
                if(img.shape==(512,512)):
                    # if(img[:,:256].mean()<img[:,256:].mean()):
                    #     flag = True
                    #     img = img[:,::-1]
                    img = np.array([img,img,img]).transpose((1,2,0))
                if img.shape[2] == 4:
                    img = img[:, :, :3]
                im = img.transpose((2, 0, 1))
                x = torch.tensor(np.asarray(im, dtype=np.float32), device='cpu', requires_grad=True).cuda() / 127.5 - 1.
                if x.shape[0] == 4:
                    x = x[:3]
                factor = x.shape[2] // im_size
                if factor != 1:
                    x = torch.nn.functional.avg_pool2d(x[None, ...], factor, factor)[0]
                assert x.shape[2] == im_size
                latents = encode(x[None, ...].cuda(),model)
                f = decode(latents,model)
                latents1 = encode(x[None, ...].cuda(),model1)
                f1 = decode(latents1,model1)

                can_f = f.detach().cpu()
                can_f1 = f1.detach().cpu()
                can_x = x[None, ...].detach().cpu()
                # if flag :
                #     can_f = torch.flip(can_f,[3])
                #     can_x = torch.flip(can_x,[3])
                r = torch.cat([can_x, can_f, can_f1], dim=3)
                canvas.append(r)
        return canvas

    def chunker_list(seq, n):
        return [seq[i * n:(i + 1) * n] for i in range((len(seq) + n - 1) // n)]

    paths = chunker_list(paths, 8 * 3)

    for i, chunk in enumerate(paths):
        canvas = make(chunk)
        canvas = torch.cat(canvas, dim=0)

        save_path = 'make_figures/output/mammogans_compare/reconstructions_%d.png' % (i)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        save_image(canvas * 0.5 + 0.5, save_path,
                   nrow=3,
                   pad_value=1.0)


if __name__ == "__main__":
    gpu_count = 1
    # cfg = get_cfg_defaults()
    # print("hi")
    run(sample, get_cfg_defaults(), description='ALAE-figure-reconstructions-paged', default_config='configs/ffhq.yaml',
        world_size=gpu_count, write_log=False)
