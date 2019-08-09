#!/usr/bin/env python3

import torch as th
from torch import nn, optim
from torch.nn import functional as F
from torchvision import transforms
from torchvision.datasets import MNIST

import learn2learn as l2l

WAYS = 3
SHOTS = 5
TASKS_PER_STEPS = 32


class Net(nn.Module):

    def __init__(self, ways=3):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(1, 20, 5, 1)
        self.conv2 = nn.Conv2d(20, 50, 5, 1)
        self.fc1 = nn.Linear(4 * 4 * 50, 500)
        self.fc2 = nn.Linear(500, ways)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.max_pool2d(x, 2, 2)
        x = F.relu(self.conv2(x))
        x = F.max_pool2d(x, 2, 2)
        x = x.view(-1, 4 * 4 * 50)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return F.log_softmax(x, dim=1)


def main(file_location="/tmp/mnist"):
    mnist_train = MNIST(file_location, train=True, download=True,
                        transform=transforms.Compose([
                            transforms.ToTensor(),
                            transforms.Normalize((0.1307,), (0.3081,)),
                            lambda x: x.view(1, 1, 28, 28),
                        ])
                        )
    mnist_test = MNIST(file_location, train=False, download=True,
                       transform=transforms.Compose([
                           transforms.ToTensor(),
                           transforms.Normalize((0.1307,), (0.3081,)),
                           lambda x: x.view(1, 1, 28, 28),
                       ])
                       )
    train_gen = l2l.data.TaskGenerator(mnist_train, ways=WAYS)
    test_gen = l2l.data.TaskGenerator(mnist_test, ways=WAYS)

    model = Net(WAYS)
    meta_model = l2l.MAML(model, lr=0.01)
    opt = optim.SGD(meta_model.parameters(), lr=0.001, momentum=0.9)
    loss = F.nll_loss

    for iteration in range(1000):
        iteration_error = 0.0
        for _ in range(TASKS_PER_STEPS):
            learner = meta_model.new()
            train_task = train_gen.sample(shots=SHOTS)
            valid_task = train_gen.sample(shots=SHOTS,
                                          classes_to_sample=train_task.sampled_classes)

            # Fast Adaptation
            for step in range(5):
                error = sum([loss(learner(X), th.tensor(y).view(-1)) for X, y in train_task])
                error /= len(train_task)
                learner.adapt(error)

            # Compute validation loss
            valid_error = sum([loss(learner(X), th.tensor(y).view(-1)) for X, y in valid_task])
            valid_error /= len(valid_task)
            iteration_error += valid_error

        iteration_error /= TASKS_PER_STEPS
        print('Valid error:', iteration_error.item())
        # Take the meta-learning step
        opt.zero_grad()
        iteration_error.backward()
        opt.step()


if __name__ == '__main__':
    import sys

    main(sys.argv[1])