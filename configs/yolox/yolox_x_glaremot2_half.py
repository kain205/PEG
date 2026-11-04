# YOLOX-X fine-tune on GlareMOT2 (official train split, first half of each seq; val = second half).
# Run inside the ByteTrack repo (its YOLOX fork: RGB mean/std preprocessing, MOTDataset), which is what the
# TrackTrack (CVPR 2025) / ByteTrack detector weights were trained with. Data from scripts/25_build_yolox_glaremot.py.
# Hyper-parameters follow ByteTrack's exps/example/mot/yolox_x_ablation.py (MOT17 half), except: fewer epochs
# because we start from a person detector (TrackTrack mot17.pth.tar), not from COCO, and eval every epoch.
import os

import torch
import torch.distributed as dist

from yolox.exp import Exp as MyExp


class Exp(MyExp):
    def __init__(self):
        super(Exp, self).__init__()
        self.num_classes = 1
        self.depth = 1.33
        self.width = 1.25
        self.exp_name = os.environ.get("YX_EXP_NAME", "yolox_x_glaremot2_half")
        self.data_dir = os.environ.get("YX_DATA", "/content/yx")
        self.train_ann = "train_half.json"
        self.val_ann = os.environ.get("YX_VAL_ANN", "val_half.json")
        self.input_size = (800, 1440)
        self.test_size = (800, 1440)
        self.random_size = (18, 32)
        self.max_epoch = int(os.environ.get("YX_EPOCHS", 20))
        self.no_aug_epochs = int(os.environ.get("YX_NO_AUG", 5))
        self.warmup_epochs = 1
        self.basic_lr_per_img = 0.001 / 64.0
        self.print_interval = 20
        self.eval_interval = 1
        self.test_conf = 0.001
        self.nmsthre = 0.7
        self.data_num_workers = 8
        self.seed = 0

    def get_data_loader(self, batch_size, is_distributed, no_aug=False):
        from yolox.data import (DataLoader, InfiniteSampler, MOTDataset, MosaicDetection, TrainTransform,
                                YoloBatchSampler)

        dataset = MOTDataset(data_dir=self.data_dir, json_file=self.train_ann, name="", img_size=self.input_size,
                             preproc=TrainTransform(rgb_means=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225),
                                                    max_labels=500))
        dataset = MosaicDetection(dataset, mosaic=not no_aug, img_size=self.input_size,
                                  preproc=TrainTransform(rgb_means=(0.485, 0.456, 0.406),
                                                         std=(0.229, 0.224, 0.225), max_labels=1000),
                                  degrees=self.degrees, translate=self.translate, scale=self.scale,
                                  shear=self.shear, perspective=self.perspective, enable_mixup=self.enable_mixup)
        self.dataset = dataset
        if is_distributed:
            batch_size = batch_size // dist.get_world_size()
        sampler = InfiniteSampler(len(self.dataset), seed=self.seed if self.seed else 0)
        batch_sampler = YoloBatchSampler(sampler=sampler, batch_size=batch_size, drop_last=False,
                                         input_dimension=self.input_size, mosaic=not no_aug)
        return DataLoader(self.dataset, num_workers=self.data_num_workers, pin_memory=True,
                          batch_sampler=batch_sampler)

    def get_eval_loader(self, batch_size, is_distributed, testdev=False):
        from yolox.data import MOTDataset, ValTransform

        valdataset = MOTDataset(data_dir=self.data_dir, json_file=self.val_ann, img_size=self.test_size, name="",
                                preproc=ValTransform(rgb_means=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)))
        if is_distributed:
            batch_size = batch_size // dist.get_world_size()
            sampler = torch.utils.data.distributed.DistributedSampler(valdataset, shuffle=False)
        else:
            sampler = torch.utils.data.SequentialSampler(valdataset)
        return torch.utils.data.DataLoader(valdataset, num_workers=self.data_num_workers, pin_memory=True,
                                           sampler=sampler, batch_size=batch_size)

    def get_evaluator(self, batch_size, is_distributed, testdev=False):
        from yolox.evaluators import COCOEvaluator

        return COCOEvaluator(dataloader=self.get_eval_loader(batch_size, is_distributed, testdev=testdev),
                             img_size=self.test_size, confthre=self.test_conf, nmsthre=self.nmsthre,
                             num_classes=self.num_classes, testdev=testdev)
