import argparse
import math
import random
import os

import numpy as np
import torch
import torchvision
from tqdm import tqdm

from results_json import ResultsJSON

import mnist_dataset
import uci_datasets
from difflogic import LogicLayer, GroupSum, PackBitsTensor, CompiledLogicNet

from torchsummary import summary


torch.set_num_threads(1)

BITS_TO_TORCH_FLOATING_POINT_TYPE = {
    16: torch.float16,
    32: torch.float32,
    64: torch.float64
}
def weighted_mse_loss(input, target):
    weight = torch.tensor(np.power(2, list(range(5))*100).reshape(-1,5)).to('cuda')
    return (weight * (input - target) ** 2).mean()


class CustomLoss(torch.nn.Module):
    def __init__(self):
        super(CustomLoss, self).__init__()

    def forward(self, output, target):
        loss = weighted_mse_loss(output, target)
        return loss
class Adder(torch.utils.data.Dataset):
    def __init__(self):
        return

    def __len__(self):
        return 10000

    def __getitem__(self, idx):
        # input is 4 bit (0 to 15) # output is 5 bit (0 to 31)
        to_add = torch.tensor(np.random.randint(16, size=2))
        result = torch.sum(to_add)

        to_add_bin_string_1 = format(to_add[0], '04b')
        to_add_bin_string_2 = format(to_add[1], '04b')
        result_bin_string = format(result, '05b')

        bin_to_add_1 = [float(to_add_bin_string_1[0]), float(to_add_bin_string_1[1]), float(to_add_bin_string_1[2]),
                        float(to_add_bin_string_1[3])]
        bin_to_add_2 = [float(to_add_bin_string_2[0]), float(to_add_bin_string_2[1]), float(to_add_bin_string_2[2]),
                        float(to_add_bin_string_2[3])]
        bin_to_add = torch.tensor(bin_to_add_1 + bin_to_add_2)

        bin_result = torch.tensor(np.array([float(result_bin_string[0]), float(result_bin_string[1]), float(result_bin_string[2]),float(result_bin_string[3]), float(result_bin_string[4])]))
        #bin_result = torch.zeros(32)
        #bin_result[result.item()]=1.
        #bin_result = bin_result.argmax(-1)
        return bin_to_add, bin_result

class VectorMultiplication(torch.utils.data.Dataset):
    def __init__(self):
        return

    def __len__(self):
        return 10000

    def __getitem__(self, idx):
        # input is 4 bit (0 to 15) # output is 9 bit (0 to 450 // [0,2*15*15])
        to_mul = torch.tensor(np.random.randint(16, size=4))
        result = torch.tensor(to_mul[0]*to_mul[2]+to_mul[1]*to_mul[3])

        to_mul_bin_string_1 = format(to_mul[0], '04b')
        to_mul_bin_string_2 = format(to_mul[1], '04b')
        to_mul_bin_string_3 = format(to_mul[2], '04b')
        to_mul_bin_string_4 = format(to_mul[3], '04b')

        result_bin_string = format(result, '09b')

        bin_to_mul_1 = [float(to_mul_bin_string_1[0]), float(to_mul_bin_string_1[1]), float(to_mul_bin_string_1[2]),
                        float(to_mul_bin_string_1[3])]
        bin_to_mul_2 = [float(to_mul_bin_string_2[0]), float(to_mul_bin_string_2[1]), float(to_mul_bin_string_2[2]),
                        float(to_mul_bin_string_2[3])]
        bin_to_mul_3 = [float(to_mul_bin_string_3[0]), float(to_mul_bin_string_3[1]), float(to_mul_bin_string_3[2]),
                        float(to_mul_bin_string_3[3])]
        bin_to_mul_4 = [float(to_mul_bin_string_4[0]), float(to_mul_bin_string_4[1]), float(to_mul_bin_string_4[2]),
                        float(to_mul_bin_string_4[3])]

        bin_to_mul = torch.tensor(bin_to_mul_1 + bin_to_mul_2 + bin_to_mul_3 + bin_to_mul_4)

        bin_result = torch.tensor(np.array([float(result_bin_string[0]), float(result_bin_string[1]), float(result_bin_string[2]),float(result_bin_string[3]), float(result_bin_string[4]),float(result_bin_string[5]),float(result_bin_string[6]),float(result_bin_string[7]),float(result_bin_string[8])]))

        return bin_to_mul, bin_result
def load_dataset(args):
    validation_loader = None
    if args.dataset == 'custom':
        train_set = Adder()
        test_set = Adder()
        train_loader = torch.utils.data.DataLoader(train_set, batch_size=100, shuffle=True)
        test_loader = torch.utils.data.DataLoader(test_set, batch_size=int(1e6), shuffle=False)
    elif args.dataset == 'vectormul':
        train_set = VectorMultiplication()
        test_set = VectorMultiplication()
        train_loader = torch.utils.data.DataLoader(train_set, batch_size=100, shuffle=True)
        test_loader = torch.utils.data.DataLoader(test_set, batch_size=int(1e6), shuffle=False)
    elif args.dataset == 'adult':
        train_set = uci_datasets.AdultDataset('./data-uci', split='train', download=True, with_val=False)
        test_set = uci_datasets.AdultDataset('./data-uci', split='test', with_val=False)
        train_loader = torch.utils.data.DataLoader(train_set, batch_size=args.batch_size, shuffle=True)
        test_loader = torch.utils.data.DataLoader(test_set, batch_size=int(1e6), shuffle=False)
    elif args.dataset == 'breast_cancer':
        train_set = uci_datasets.BreastCancerDataset('./data-uci', split='train', download=True, with_val=False)
        test_set = uci_datasets.BreastCancerDataset('./data-uci', split='test', with_val=False)
        train_loader = torch.utils.data.DataLoader(train_set, batch_size=args.batch_size, shuffle=True)
        test_loader = torch.utils.data.DataLoader(test_set, batch_size=int(1e6), shuffle=False)
    elif args.dataset.startswith('monk'):
        style = int(args.dataset[4])
        train_set = uci_datasets.MONKsDataset('./data-uci', style, split='train', download=True, with_val=False)
        test_set = uci_datasets.MONKsDataset('./data-uci', style, split='test', with_val=False)
        train_loader = torch.utils.data.DataLoader(train_set, batch_size=args.batch_size, shuffle=True)
        test_loader = torch.utils.data.DataLoader(test_set, batch_size=int(1e6), shuffle=False)
    elif args.dataset in ['mnist', 'mnist20x20']:
        train_set = mnist_dataset.MNIST('./data-mnist', train=True, download=True, remove_border=args.dataset == 'mnist20x20')
        test_set = mnist_dataset.MNIST('./data-mnist', train=False, remove_border=args.dataset == 'mnist20x20')

        train_set_size = math.ceil((1 - args.valid_set_size) * len(train_set))
        valid_set_size = len(train_set) - train_set_size
        train_set, validation_set = torch.utils.data.random_split(train_set, [train_set_size, valid_set_size])

        train_loader = torch.utils.data.DataLoader(train_set, batch_size=args.batch_size, shuffle=True, pin_memory=True, drop_last=True, num_workers=4)
        validation_loader = torch.utils.data.DataLoader(validation_set, batch_size=args.batch_size, shuffle=False, pin_memory=True, drop_last=True)
        test_loader = torch.utils.data.DataLoader(test_set, batch_size=args.batch_size, shuffle=False, pin_memory=True, drop_last=True)
    elif 'cifar-10' in args.dataset:
        transform = {
            'cifar-10-3-thresholds': lambda x: torch.cat([(x > (i + 1) / 4).float() for i in range(3)], dim=0),
            'cifar-10-31-thresholds': lambda x: torch.cat([(x > (i + 1) / 32).float() for i in range(31)], dim=0),
        }[args.dataset]
        transforms = torchvision.transforms.Compose([
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Lambda(transform),
        ])
        train_set = torchvision.datasets.CIFAR10('./data-cifar', train=True, download=True, transform=transforms)
        test_set = torchvision.datasets.CIFAR10('./data-cifar', train=False, transform=transforms)

        train_set_size = math.ceil((1 - args.valid_set_size) * len(train_set))
        valid_set_size = len(train_set) - train_set_size
        train_set, validation_set = torch.utils.data.random_split(train_set, [train_set_size, valid_set_size])

        train_loader = torch.utils.data.DataLoader(train_set, batch_size=args.batch_size, shuffle=True, pin_memory=True, drop_last=True, num_workers=4)
        validation_loader = torch.utils.data.DataLoader(validation_set, batch_size=args.batch_size, shuffle=False, pin_memory=True, drop_last=True)
        test_loader = torch.utils.data.DataLoader(test_set, batch_size=args.batch_size, shuffle=False, pin_memory=True, drop_last=True)

    else:
        raise NotImplementedError(f'The data set {args.dataset} is not supported!')

    return train_loader, validation_loader, test_loader


def load_n(loader, n):
    i = 0
    while i < n:
        for x in loader:
            yield x
            i += 1
            if i == n:
                break


def input_dim_of_dataset(dataset):
    return {
        'vectormul':16,
        'custom': 8,
        'adult': 116,
        'breast_cancer': 51,
        'monk1': 17,
        'monk2': 17,
        'monk3': 17,
        'mnist': 784,
        'mnist20x20': 400,
        'cifar-10-3-thresholds': 3 * 32 * 32 * 3,
        'cifar-10-31-thresholds': 3 * 32 * 32 * 31,
    }[dataset]


def num_classes_of_dataset(dataset):
    return {
        'vectormul': 9,
        'custom': 5,
        'adult': 2,
        'breast_cancer': 2,
        'monk1': 2,
        'monk2': 2,
        'monk3': 2,
        'mnist': 10,
        'mnist20x20': 10,
        'cifar-10-3-thresholds': 10,
        'cifar-10-31-thresholds': 10,
    }[dataset]


def get_model(args):
    llkw = dict(grad_factor=args.grad_factor, connections=args.connections)

    in_dim = input_dim_of_dataset(args.dataset)
    class_count = num_classes_of_dataset(args.dataset)

    logic_layers = []

    arch = args.architecture
    k = args.num_neurons
    l = args.num_layers

    ####################################################################################################################

    if arch == 'randomly_connected':
        logic_layers.append(torch.nn.Flatten())
        logic_layers.append(LogicLayer(in_dim=in_dim, out_dim=k, **llkw))
        for _ in range(l - 1):
            logic_layers.append(LogicLayer(in_dim=k, out_dim=k, **llkw))

        model = torch.nn.Sequential(
            *logic_layers,
            GroupSum(class_count, args.tau)
        )

    ####################################################################################################################

    else:
        raise NotImplementedError(arch)

    ####################################################################################################################

    total_num_neurons = sum(map(lambda x: x.num_neurons, logic_layers[1:-1]))
    print(f'total_num_neurons={total_num_neurons}')
    total_num_weights = sum(map(lambda x: x.num_weights, logic_layers[1:-1]))
    print(f'total_num_weights={total_num_weights}')
    if args.experiment_id is not None:
        results.store_results({
            'total_num_neurons': total_num_neurons,
            'total_num_weights': total_num_weights,
        })

    model = model.to('cuda')

    print(model)
    if args.experiment_id is not None:
        results.store_results({'model_str': str(model)})

    #loss_fn = torch.nn.CrossEntropyLoss()
    #loss_fn = torch.nn.MSELoss()
    loss_fn = CustomLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

    return model, loss_fn, optimizer


def train(model, x, y, loss_fn, optimizer):
    x = model(x)
    loss = loss_fn(x.float(), y.float())
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    return loss.item()


def eval(model, loader, mode):
    orig_mode = model.training
    with torch.no_grad():
        model.train(mode=mode)
        if args.dataset == 'custom':
            print(model(x.to('cuda')).round().to(torch.float32).size())
            res = torch.tensor([
                #(model(x.to('cuda').round()).argmax(-1) == y.to('cuda')).to(torch.float32).mean().item()
                #((model(x.to('cuda').round()) == y.to('cuda')).to(torch.float32)).sum().item() / 500
                ((torch.tensor(np.power(2, list(range(5)) * 100).reshape(-1, 5)) * model(x.to('cuda')).round().to(torch.float32).cpu()) - (y * torch.tensor(np.power(2, list(range(5)) * 100).reshape(-1, 5)).to(torch.float32))).mean(dim=0)
            for x, y in loader
            ]).reshape(-1,5).mean(dim=0)
        elif args.dataset == 'vectormul':
            res = np.mean(
                [
                    # (model(x.to('cuda').round()).argmax(-1) == y.to('cuda')).to(torch.float32).mean().item()
                    ((model(x.to('cuda').round()) == y.to('cuda')).to(torch.float32)).sum().item() / 900

                    for x, y in loader
                ])
        else:
            res = np.mean(
                [
                    (model(x.to('cuda').round()).argmax(-1) == y.to('cuda')).to(torch.float32).mean().item()

                    for x, y in loader
                ])

        print(model)
        for name, param in model.named_parameters():
            print(name)
            print(param.argmax(-1))
        model.train(mode=orig_mode)

    return res.item()


def packbits_eval(model, loader):
    orig_mode = model.training
    with torch.no_grad():
        model.eval()
        res = np.mean(
            [
                #(model(PackBitsTensor(x.to('cuda').round().bool())).argmax(-1) == y.to('cuda')).to(torch.float32).mean().item()
                ((model(x.to('cuda').round()) == y.to('cuda')).to(torch.float32)).sum().item() / 5

                for x, y in loader
            ]
        )
        model.train(mode=orig_mode)
    return res.item()


if __name__ == '__main__':

    ####################################################################################################################

    parser = argparse.ArgumentParser(description='Train logic gate network on the various datasets.')

    parser.add_argument('-eid', '--experiment_id', type=int, default=None)

    parser.add_argument('--dataset', type=str, choices=[
        'vectormul',
        'custom',
        'adult', 'breast_cancer',
        'monk1', 'monk2', 'monk3',
        'mnist', 'mnist20x20',
        'cifar-10-3-thresholds',
        'cifar-10-31-thresholds',
    ], required=True, help='the dataset to use')
    parser.add_argument('--tau', '-t', type=float, default=10, help='the softmax temperature tau')
    parser.add_argument('--seed', '-s', type=int, default=0, help='seed (default: 0)')
    parser.add_argument('--batch-size', '-bs', type=int, default=128, help='batch size (default: 128)')
    parser.add_argument('--learning-rate', '-lr', type=float, default=0.01, help='learning rate (default: 0.01)')
    parser.add_argument('--training-bit-count', '-c', type=int, default=32, help='training bit count (default: 32)')

    parser.add_argument('--implementation', type=str, default='cuda', choices=['cuda', 'python'],
                        help='`cuda` is the fast CUDA implementation and `python` is simpler but much slower '
                        'implementation intended for helping with the understanding.')

    parser.add_argument('--packbits_eval', action='store_true', help='Use the PackBitsTensor implementation for an '
                                                                     'additional eval step.')
    parser.add_argument('--compile_model', action='store_true', help='Compile the final model with C for CPU.')

    parser.add_argument('--num-iterations', '-ni', type=int, default=100_000, help='Number of iterations (default: 100_000)')
    parser.add_argument('--eval-freq', '-ef', type=int, default=2_000, help='Evaluation frequency (default: 2_000)')

    parser.add_argument('--valid-set-size', '-vss', type=float, default=0., help='Fraction of the train set used for validation (default: 0.)')
    parser.add_argument('--extensive-eval', action='store_true', help='Additional evaluation (incl. valid set eval).')

    parser.add_argument('--connections', type=str, default='unique', choices=['random', 'unique'])
    parser.add_argument('--architecture', '-a', type=str, default='randomly_connected')
    parser.add_argument('--num_neurons', '-k', type=int)
    parser.add_argument('--num_layers', '-l', type=int)

    parser.add_argument('--grad-factor', type=float, default=1.)

    args = parser.parse_args()

    ####################################################################################################################

    print(vars(args))

    assert args.num_iterations % args.eval_freq == 0, (
        f'iteration count ({args.num_iterations}) has to be divisible by evaluation frequency ({args.eval_freq})'
    )

    if args.experiment_id is not None:
        assert 520_000 <= args.experiment_id < 530_000, args.experiment_id
        results = ResultsJSON(eid=args.experiment_id, path='./results/')
        results.store_args(args)

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)

    train_loader, validation_loader, test_loader = load_dataset(args)
    model, loss_fn, optim = get_model(args)

    ####################################################################################################################

    best_acc = 0
    epoch_loss = 0
    for i, (x, y) in tqdm(
            enumerate(load_n(train_loader, args.num_iterations)),
            desc='iteration',
            total=args.num_iterations,
    ):
        x = x.to(BITS_TO_TORCH_FLOATING_POINT_TYPE[args.training_bit_count]).to('cuda')
        y = y.to('cuda')

        loss = train(model, x, y, loss_fn, optim)
        epoch_loss += loss

        if (i+1) % args.eval_freq == 0:
            print("\n")
            print(epoch_loss)
            epoch_loss = 0
            if args.extensive_eval:
                train_accuracy_train_mode = eval(model, train_loader, mode=True)
                valid_accuracy_eval_mode = eval(model, validation_loader, mode=False)
                valid_accuracy_train_mode = eval(model, validation_loader, mode=True)
            else:
                train_accuracy_train_mode = -1
                valid_accuracy_eval_mode = -1
                valid_accuracy_train_mode = -1
            train_accuracy_eval_mode = eval(model, train_loader, mode=False)
            test_accuracy_eval_mode = eval(model, test_loader, mode=False)
            test_accuracy_train_mode = eval(model, test_loader, mode=True)

            r = {
                'train_acc_eval_mode': train_accuracy_eval_mode,
                'train_acc_train_mode': train_accuracy_train_mode,
                'valid_acc_eval_mode': valid_accuracy_eval_mode,
                'valid_acc_train_mode': valid_accuracy_train_mode,
                'test_acc_eval_mode': test_accuracy_eval_mode,
                'test_acc_train_mode': test_accuracy_train_mode,
            }

            if args.packbits_eval:
                r['train_acc_eval'] = packbits_eval(model, train_loader)
                r['valid_acc_eval'] = packbits_eval(model, train_loader)
                r['test_acc_eval'] = packbits_eval(model, test_loader)

            if args.experiment_id is not None:
                results.store_results(r)
            else:
                print(r)

            if valid_accuracy_eval_mode > best_acc:
                best_acc = valid_accuracy_eval_mode
                if args.experiment_id is not None:
                    results.store_final_results(r)
                else:
                    print('IS THE BEST UNTIL NOW.')

            if args.experiment_id is not None:
                results.save()

    ####################################################################################################################

    if args.compile_model:
        print('\n' + '='*80)
        print(' Converting the model to C code and compiling it...')
        print('='*80)

        for opt_level in range(4):

            for num_bits in [
                # 8,
                # 16,
                # 32,
                64
            ]:
                os.makedirs('lib', exist_ok=True)
                save_lib_path = 'lib/{:08d}_{}.so'.format(
                    args.experiment_id if args.experiment_id is not None else 0, num_bits
                )

                compiled_model = CompiledLogicNet(
                    model=model,
                    num_bits=num_bits,
                    cpu_compiler='gcc',
                    # cpu_compiler='clang',
                    verbose=True,
                )

                compiled_model.compile(
                    opt_level=1 if args.num_layers * args.num_neurons < 50_000 else 0,
                    save_lib_path=save_lib_path,
                    verbose=True
                )

                correct, total = 0, 0
                with torch.no_grad():
                    for (data, labels) in torch.utils.data.DataLoader(test_loader.dataset, batch_size=int(1e6), shuffle=False):
                        data = torch.nn.Flatten()(data).bool().numpy()

                        output = compiled_model(data, verbose=True)

                        correct += (output.argmax(-1) == labels).float().sum()
                        total += output.shape[0]

                acc3 = correct / total
                print('COMPILED MODEL', num_bits, acc3)

