import os
import shutil
import yaml
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F

import numpy as np
from tqdm import tqdm
from skimage import img_as_ubyte
from natsort import natsorted
from glob import glob
import utils_tool

from basicsr.models.archs.kbnet_s_arch import KBNet_s
from basicsr.utils.util import patch_forward

import cv2

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

def imread(img_path):
  img = cv2.imread(img_path)
  img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
  return img

parser = argparse.ArgumentParser(description='Gasussian Grayscale Denoising using Restormer')

parser.add_argument('--input_dir', default='/content/drive/MyDrive/', type=str, help='Directory of validation images')
parser.add_argument('--result_dir', default='/content/drive/MyDrive/KBNetResult', type=str,
                    help='Directory for results')
parser.add_argument('--yml', default='None', type=str, help='Sigma values')
args = parser.parse_args()

factor = 8

yaml_file = args.yml
x = yaml.load(open(yaml_file, mode='r'), Loader=Loader)

sigmas = [x['datasets']['train']['sigma_range']]

cfg_name = os.path.basename(yaml_file).split('.')[0]

pth_path = x['path']['pretrain_network_g']
print('**', yaml_file, pth_path)

s = x['network_g'].pop('type')

model_restoration = eval(s)(**x['network_g'])
checkpoint = torch.load(pth_path)

print("===>Testing using weights: ")
model_restoration.cuda()
model_restoration = nn.DataParallel(model_restoration)
model_restoration.load_state_dict(checkpoint['net'])
model_restoration.eval()

datasets = ['test_folder']

for sigma_test in sigmas:
    print("Compute results for noise level", sigma_test)

    for dataset in datasets:
        inp_dir = os.path.join(args.input_dir, dataset)
        files = natsorted(glob(os.path.join(inp_dir, '*.png')) + glob(os.path.join(inp_dir, '*.tiff')))
        result_dir_tmp = os.path.join(args.result_dir, 'gray')
        os.makedirs(result_dir_tmp, exist_ok=True)

        psnr_list = []

        with torch.no_grad():
            for file_ in tqdm(files):
                torch.cuda.ipc_collect()
                torch.cuda.empty_cache()
                gt = utils_tool.load_gray_img(file_)
                img = np.float32(gt) / 255.

                np.random.seed(seed=0)  # for reproducibility
                img += np.random.normal(0, sigma_test / 255., img.shape)

                noisy = torch.from_numpy(img)

                gtnoisy_path = os.path.join(args.result_dir, 'gray_ori')
                os.makedirs(gtnoisy_path, exist_ok=True)
                shutil.copyfile(file_, os.path.join(gtnoisy_path, dataset + os.path.basename(file_)))
                utils_tool.save_img(
                    os.path.join(gtnoisy_path, os.path.basename(file_).split('.')[0] + '-noisy.tiff'),
                    img_as_ubyte(noisy.clip(0, 1)))

        #print(dataset, np.mean(psnr_list))
