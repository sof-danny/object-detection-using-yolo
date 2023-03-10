"""This is the loss function. The heart of YOLO"""
import torch
import torch.nn as nn
import torch.nn.functional as F

def compute_iou(box1, box2):
    """Compute the intersection over union of two set of boxes, each box is [x1,y1,x2,y2].
    Args:
      box1: (tensor) bounding boxes, sized [N,4].
      box2: (tensor) bounding boxes, sized [M,4].
    Return:
      (tensor) iou, sized [N,M].
    """
    N = box1.size(0)
    M = box2.size(0)

    lt = torch.max(
        box1[:, :2].unsqueeze(1).expand(N, M, 2),  # [N,2] -> [N,1,2] -> [N,M,2]
        box2[:, :2].unsqueeze(0).expand(N, M, 2),  # [M,2] -> [1,M,2] -> [N,M,2]
    )

    rb = torch.min(
        box1[:, 2:].unsqueeze(1).expand(N, M, 2),  # [N,2] -> [N,1,2] -> [N,M,2]
        box2[:, 2:].unsqueeze(0).expand(N, M, 2),  # [M,2] -> [1,M,2] -> [N,M,2]
    )

    wh = rb - lt  # [N,M,2]
    wh[wh < 0] = 0  # clip at 0
    inter = wh[:, :, 0] * wh[:, :, 1]  # [N,M]

    area1 = (box1[:, 2] - box1[:, 0]) * (box1[:, 3] - box1[:, 1])  # [N,]
    area2 = (box2[:, 2] - box2[:, 0]) * (box2[:, 3] - box2[:, 1])  # [M,]
    area1 = area1.unsqueeze(1).expand_as(inter)  # [N,] -> [N,1] -> [N,M]
    area2 = area2.unsqueeze(0).expand_as(inter)  # [M,] -> [1,M] -> [N,M]

    iou = inter / (area1 + area2 - inter)
    return iou




class YoloLoss(nn.Module):
    def __init__(self, S, B, l_coord, l_noobj):
        super(YoloLoss, self).__init__()
        self.S = S
        self.B = B
        self.C = 20
        self.l_coord = l_coord
        self.l_noobj = l_noobj

    def xywh2xyxy(self, boxes):
        """
        Parameters:
        boxes: (N,4) representing by x,y,w,h

        Returns:
        boxes: (N,4) representing by x1,y1,x2,y2

        if for a Box b the coordinates are represented by [x, y, w, h] then
        x1, y1 = x/S - 0.5*w, y/S - 0.5*h ; x2,y2 = x/S + 0.5*w, y/S + 0.5*h
        Note: Over here initially x, y are the center of the box and w,h are width and height.
        """
        ### CODE ###
        
        boxes[:,0] = boxes[:,0] / self.S - 0.5 * boxes[:,2]
        boxes[:,1] = boxes[:,1] / self.S - 0.5 * boxes[:,3]
        boxes[:,2] = boxes[:,0] / self.S + 0.5 * boxes[:,2]
        boxes[:,3] = boxes[:,1] / self.S + 0.5 * boxes[:,3]
        
        return boxes

    def find_best_iou_boxes(self, pred_box_list, box_target):
        """
        Parameters:
        box_pred_list : [(tensor) size (-1, 5) ...]
        box_target : (tensor)  size (-1, 4)

        Returns:
        best_iou: (tensor) size (-1, 1)
        best_boxes : (tensor) size (-1, 5), containing the boxes which give the best iou among the two (self.B) predictions

        Hints:
        1) Find the iou's of each of the 2 bounding boxes of each grid cell of each image.
        2) For finding iou's use the compute_iou function
        3) use xywh2xyxy to convert bbox format if necessary,
        Note: Over here initially x, y are the center of the box and w,h are width and height.
        We perform this transformation to convert the correct coordinates into bounding box coordinates.
        """

        ### CODE ###
       
        best_boxes = pred_box_list[0]
        for i in range(0, box_target.size()[0], 2):
            box1 , box2 = self.xywh2xyxy(pred_box_list[0].clone().view(-1,5)[:,:4]), self.xywh2xyxy(pred_box_list[1].clone().view(-1,5)[:,:4])
            box_target = self.xywh2xyxy(box_target.clone().view(-1,4))
            
            iou1 = compute_iou(box1, box_target)
            iou2 = compute_iou(box2, box_target)
            ious = torch.cat([iou1,iou2], dim=0 )
            best_ious,_= torch.max(ious, dim =0)
            
            if iou1[i][i]<iou2[i][i]:
              best_boxes[i]=pred_box_list[1][i]
            return best_ious,best_boxes

    def get_class_prediction_loss(self,classes_pred, classes_target, has_object_map):
        # Your code here
        
        get_class_loss = F.mse_loss(classes_pred, classes_target, reduction='sum')
        return get_class_loss
        
    def get_no_object_loss(self, pred_boxes_list, has_object_map):
        """
        Parameters:
        pred_boxes_list: (list) [(tensor) size (N, S, S, 5)  for B pred_boxes]
        has_object_map: (tensor) size (N, S, S)
        
        
        Returns:
        loss : scalar

        Hints:
        1) Only compute loss for cell which doesn't contain object
        2) compute loss for all predictions in the pred_boxes_list list
        3) You can assume the ground truth confidence of non-object cells is 0
        """
        
        ### CODE ###
        no_object_mask = ~has_object_map
        
        no_object_boxes1 = pred_boxes_list[0][no_object_mask]
        no_object_boxes2 = pred_boxes_list[1][no_object_mask]
        
        no_object_pred_conf = torch.cat((no_object_boxes1[:,4:5], no_object_boxes2[:,4:5]), 0)
        
        no_object_target_conf = torch.zeros_like(no_object_pred_conf)
        
        no_object_loss = F.mse_loss(no_object_pred_conf, no_object_target_conf, reduction='sum')
        
        return no_object_loss
        

    def get_contain_conf_loss(self, box_pred_conf, box_target_conf):
        """
        Parameters:
        box_pred_conf : (tensor) size (-1,1)
        box_target_conf: (tensor) size (-1,1)

        Returns:
        contain_loss : scalar

        Hints:
        The box_target_conf should be treated as ground truth, i.e., no gradient

        """
        ### CODE
        # your code here
        
        
        contain_loss = F.mse_loss(box_pred_conf, box_target_conf, reduction='sum')
        return contain_loss

    def get_regression_loss(self, box_pred_response, box_target_response):
        """
        Parameters:
        box_pred_response : (tensor) size (-1, 4)
        box_target_response : (tensor) size (-1, 4)
        Note : -1 corresponds to ravels the tensor into the dimension specified
        See : https://pytorch.org/docs/stable/tensors.html#torch.Tensor.view_as

        Returns:
        reg_loss : scalar

        """
        ### CODE
        pred_xy = box_pred_response[:,:2]
        pred_wh = torch.sqrt(box_pred_response[:,2:])
        target_xy = box_target_response[:,:2]
        target_wh = torch.sqrt(box_target_response[:,2:])
        loss_xy = F.mse_loss(pred_xy, target_xy, reduction = 'sum')
        loss_wh = F.mse_loss(pred_wh, target_wh, reduction ='sum')
        reg_loss = loss_xy+loss_wh
        return reg_loss

    def forward(self, pred_tensor, target_boxes, target_cls, has_object_map):
        """
        pred_tensor: (tensor) size(N,S,S,Bx5+20=30) N:batch_size
                      where B - number of bounding boxes this grid cell is a part of = 2
                            5 - number of bounding box values corresponding to [x, y, w, h, c]
                                where x - x_coord, y - y_coord, w - width, h - height, c - confidence of having an object
                            20 - number of classes

        target_boxes: (tensor) size (N, S, S, 4): the ground truth bounding boxes
        target_cls: (tensor) size (N, S, S, 20): the ground truth class
        has_object_map: (tensor, bool) size (N, S, S): the ground truth for whether each cell contains an object (True/False)

        Returns:
        loss_dict (dict): with key value stored for total_loss, reg_loss, containing_obj_loss, no_obj_loss and cls_loss
        """
        N = pred_tensor.size(0)
        total_loss = 0.0
        
        
        # split the pred tensor from an entity to separate tensors:
        # -- pred_boxes_list: a list containing all bbox prediction (list) [(tensor) size (N, S, S, 5)  for B pred_boxes]
                # -- pred_cls (containing all classification prediction)
        pred_tensor1 = pred_tensor[:,:,:,:5] #for bbox 1
        pred_tensor2 = pred_tensor[:,:,:,5:10] #for bbox 2
        
        pred_cls = pred_tensor[:,:,:,10:] #pred class
        pred_cls = pred_cls[has_object_map]
        
        pred_boxes_list = [pred_tensor1, pred_tensor2] #box containing all bbox predictions
        
        # compcute classification loss
        target_cls =target_cls[has_object_map]
        class_loss = self.get_class_prediction_loss(pred_cls, target_cls, has_object_map)
        
        # compute no-object loss
        
        no_object_loss = self.get_no_object_loss(pred_boxes_list, has_object_map)
   
        
        # Re-shape boxes in pred_boxes_list and target_boxes to meet the following desires
        # 1) only keep having-object cells
        # 2) vectorize all dimensions except for the last one for faster computation
        pred_tensor1 = pred_tensor1[has_object_map].view(-1,5)
        pred_tensor2 = pred_tensor2[has_object_map].view(-1,5)
        
        pred_box_list = [pred_tensor1, pred_tensor2]
        target_boxes = target_boxes[has_object_map].clone()
        
        # find the best boxes among the 2 (or self.B) predicted boxes and the corresponding iou
        
        best_ious, best_boxes = self.find_best_iou_boxes(pred_box_list, target_boxes)
        
        # compute regression loss between the found best bbox and GT bbox for all the cell containing objects
        
        box_prediction_response = best_boxes[:,:4]
        box_target_response = target_boxes

        reg_loss = self.get_regression_loss(box_prediction_response, box_target_response)
        
        # compute contain_object_loss
        box_pred_conf  = best_boxes[:,4:5]
        box_target_conf = best_ious.view(-1,1)
        box_target_conf = box_target_conf.detach()
        contain_loss = self.get_contain_conf_loss(box_pred_conf, box_target_conf)
        
        # compute final loss
        total_loss = (self.l_coord * reg_loss + contain_loss + self.l_noobj * no_object_loss + class_loss) / N
        # construct return loss_dict
        loss_dict = dict(
            total_loss= total_loss,
            reg_loss=reg_loss,
            containing_obj_loss=contain_loss,
            no_obj_loss=no_object_loss,
            cls_loss=class_loss,
        )
        return loss_dict



