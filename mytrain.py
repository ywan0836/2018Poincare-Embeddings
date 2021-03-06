#!/usr/bin/env python3
# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#

import numpy as np
import timeit
from torch.utils.data import DataLoader
import gc

_lr_multiplier = 0.01


def train_mp(model, data, optimizer, opt, log, rank, mvalue, queue):
    try:
        train(model, data, optimizer, opt, log, rank, mvalue, queue)
    except Exception as err:
        log.exception(err)
        queue.put(None)


def train(model, data, optimizer, opt, log, rank=1, mvalue = 2.0, queue=None):
    # setup parallel data loader
    loader = DataLoader(
        data,
        batch_size=opt.batchsize,
        shuffle=True,
        num_workers=opt.ndproc,
        collate_fn=data.collate
    )

    for epoch in range(opt.epochs):
        epoch_loss = []
        loss = None
        data.burnin = False
        lr = opt.lr
        t_start = timeit.default_timer()
        if epoch < opt.burnin:
            data.burnin = True
            # Slow down the learning speed by 100 times
            lr = opt.lr * _lr_multiplier
            if rank == 1:
                log.info(f'Burnin: lr={lr}')
                      
        for inputs, targets in loader:
            # Time spent so far
            elapsed = timeit.default_timer() - t_start
            # Reset the gradients otherwise they would be accumulated
            optimizer.zero_grad()
            # Make the predictions
            preds = model(inputs)
            # Calculate the loss
            loss = model.loss(preds, mvalue)
            # Backpropagation
            loss.backward()
            # Gradient Descent
            optimizer.step(lr=lr)
            # Record the loss for each epoch
            epoch_loss.append(loss.item())   #(data[0])
        if rank == 1:
            emb = None
            # Store the model for the final epoch and the evaluation epoch
            if epoch == (opt.epochs - 1) or epoch % opt.eval_each == (opt.eval_each - 1):
                emb = model
            if queue is not None:
                queue.put(
                    (epoch, elapsed, np.mean(epoch_loss), emb)
                )
            else:
                log.info(
                    'info: {'
                    f'"elapsed": {elapsed}, '
                    f'"loss": {np.mean(epoch_loss)}, '
                    '}'
                )
        gc.collect()
