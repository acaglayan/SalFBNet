import cv2, os, glob
from PIL import Image
from torch import nn
import torch.nn.functional as F
from torchvision import transforms
import torch
from loss_utils import calc_loss_unisal, calc_loss_unisal_val, log_softmax, softmax

# loss function
class Loss(nn.Module):
    def __init__(self, weight=0.1):
        super(Loss, self).__init__()
        self.weight = weight
        self.loss_metrics = ('kld', 'nss', 'cc', 'sfne')
        self.cuda = True
        if self.cuda:
            self.device = torch.device('cuda:0')
    

    def forward(self, label, f_score, fix, nonfix):
        
        sal = label
        f_score = f_score + 1e-7*torch.randn(f_score.shape).to(self.device)
        f_score = F.interpolate(f_score, size=(label.shape[-2], label.shape[-1]), mode='bilinear')
        loss_mse = self.MSE_loss(f_score, sal)

        loss=calc_loss_unisal(pred_seq=f_score, sal=sal, fix=fix, nonfix=nonfix, loss_metrics=['kld', 'cc', 'sfne'],loss_weights=(1, 0.1, 0.025))
        loss += 0.025*loss_mse
        return loss

    def MSE_loss(self, pred_seq, gt):

        sal = torch.reshape(pred_seq, (pred_seq.shape[0], pred_seq.shape[1] * pred_seq.shape[2] * pred_seq.shape[3]))
        max_sal = torch.max(sal, dim=1)[0]
        # print(max_sal)
        sal = sal / (torch.reshape(max_sal, (sal.shape[0], 1)) + 1e-4)

        gt_sal = torch.reshape(gt, (gt.shape[0], gt.shape[1] * gt.shape[2] * gt.shape[3]))
        saliency_loss = torch.mean(torch.square(((sal - gt_sal) / (1.1 - gt_sal)) + 1e-4))
        return saliency_loss

    def loss_list(self, pred_seq, fix, sal):
        loss_ls = torch.zeros([1]).to(self.device)
        for pred in pred_seq:
            pred = pred.float()
            ls = self.loss_single(pred, fix, sal)
            loss_ls += ls
        loss_list=loss_ls/torch.tensor(len(pred_seq))
        # loss_list = sum(l for l in loss_ls) / len(pred_seq)
        return loss_list

    def loss_single(self, pred_fusion, fix, sal):
        loss_fusion = self.MSE_loss(pred_fusion, sal)
        return loss_fusion


if __name__ == '__main__':
    data_root='/media/ra-pc/datadisk4tb1/Data/Datasets/2D_Image_Saliency/SALICON/'
    gt_map_root=os.path.join(data_root, 'maps', 'val')
    gt_fix_root=os.path.join(data_root, 'fixations', 'val')
    gt_map_list=sorted(glob.glob(os.path.join(gt_map_root, "*.png")))
    gt_fix_list = sorted(glob.glob(os.path.join(gt_fix_root, "*.png")))
    fbloss=Loss()

    for gt_map_path, gt_fix_path in zip(gt_map_list, gt_fix_list):
        t_transform = transforms.Compose([
            transforms.ToTensor()])
        gt_map = t_transform(Image.open(gt_map_path).convert('L'))
        gt_map = torch.unsqueeze(gt_map, 0)   #[b, c, w, h]
        gt_fix = t_transform(Image.open(gt_fix_path).convert('L'))
        gt_fix = torch.unsqueeze(gt_fix, 0)  #[b, c, w, h]
        pred=torch.randn(1, 1, 480, 640)
        # pred = gt_map  # using log_softmax as input for the kld loss
        loss=fbloss.forward(label=gt_map.to(fbloss.device), f_score=pred.to(fbloss.device), fix=gt_fix.to(fbloss.device), nonfix=gt_fix)
        print('done')
