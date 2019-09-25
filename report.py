import os
import jinja2
from subprocess import Popen
import tempfile
import shutil
import json
import matplotlib.pyplot as plt
import tikzplotlib
from datetime import datetime
from numpy import linspace

latex_jinja_env = jinja2.Environment(
    block_start_string='\BLOCK{',
    block_end_string='}',
    variable_start_string='\VAR{',
    variable_end_string='}',
    comment_start_string='\#{',
    comment_end_string='}',
    line_statement_prefix='%%',
    line_comment_prefix='%#',
    trim_blocks=True,
    autoescape=False,
    loader=jinja2.FileSystemLoader('./latex'))


def get_tikz_strings(model_dict, do_hist=True):
    epochs = [ep+1 for ep in list(range(model_dict['training']['epochs']))]
    hist = model_dict['training']['history']

    # accuracies
    plt.close()
    plt.figure()
    for key in model_dict['training']['metrics']:
        key_disp_stem = key.replace('_', ' ').capitalize()
        if key=='accuracy':
            key = 'acc'

        for metric in [key, 'val_'+key]:
            if metric[:3]=='val':
                marker = 'o--'
                metric_disp = 'Test ' + key_disp_stem
            else:
                marker = 'x--'
                metric_disp = 'Training ' + key_disp_stem

            # x axis
            xmin, xmax = epochs[0]-.5, epochs[-1]+.5
            plt.xlabel('Epoch')
            plt.xticks(epochs)

            #y axis
            if len(model_dict['training']['metrics']) > 1:
                plt.ylabel('Metric')
            else:
                plt.ylabel(metric_disp)
            min_metric = float(min(hist[metric]))
            ymin, ymax = .9*min(round(min_metric, 1), 0.8), 1.025
            yval = [float(val) for val in hist[metric]]

            # axis limits
            plt.axis([xmin, xmax, ymin, ymax])
            # plot
            plt.plot(epochs[:len(yval)], yval, marker, label=metric_disp,
                                           markersize=5,
                                           linewidth=1)
        # horizontal line at y=1
    plt.plot([xmin, xmax], [1., 1.], 'k:', linewidth=1)
    plt.title(r'{\bf Progression of Evaluation metrics}')
    plt.legend(loc='lower right')
    tikz_acc = tikzplotlib.get_tikz_code(extra_axis_parameters={'font=\small'},
                                         strict=True)

    # loss
    plt.close()
    fig = plt.figure()
    for metric in ['loss', 'val_loss']:
        metric_disp = 'Training Loss' if metric=='loss' else 'Test Loss'

        marker = 'o--' if metric[:3]=='val' else 'x--'

        # x axis
        xmin, xmax = epochs[0]-.5, epochs[-1]+.5
        plt.xlabel('Epoch')
        plt.xticks(epochs)

        #y axis
        plt.ylabel('Loss')
        min_metric, max_metric = float(min(hist[metric])), float(max(hist[metric]))
        ymin, ymax = .6*min(round(min_metric, 1), 0.5), max_metric*1.3
        yval = [float(val) for val in hist[metric]]


        # axis limits
        plt.axis([xmin, xmax, ymin, ymax])
        # plot
        plt.plot(epochs[:len(yval)], yval, marker, label=metric_disp,
                                       markersize=5,
                                       linewidth=1)
    plt.legend(loc='upper right')
    plt.title(r'{\bf Progression of loss function}')
    tikz_loss = tikzplotlib.get_tikz_code(extra_axis_parameters={'font=\small'},
                                         strict=True)

    ######################################
    # learning rate
    plt.close()
    plt.figure()

    # x axis
    xmin, xmax = epochs[0]-.5, epochs[-1]+.5
    plt.xlabel('Epoch')
    plt.xticks(epochs)

    #y axis
    plt.ylabel('Learning Rate')
    min_lr, max_lr = float(min(hist['lr'])), float(max(hist['lr']))
    ymin, ymax = .6*min(round(min_lr, 1), 0.5), max_lr*1.3
    yval = [float(val) for val in hist['lr']]

    # axis limits
    plt.axis([xmin, xmax, ymin, ymax])
    # plot
    plt.plot(epochs[:len(yval)], yval, marker, label='Learning Rate',
                                   markersize=5,
                                   linewidth=1)
    plt.legend(loc='upper right')
    plt.title(r'{\bf Progression of Learning rate}')
    tikz_lr = tikzplotlib.get_tikz_code(extra_axis_parameters={'font=\small'},
                                         strict=True)

    out_dict = {'loss': tikz_loss, 'acc': tikz_acc, 'lr': tikz_lr}
    return out_dict


def str_to_latex(string):
    return string.replace('\\', r'\textbackslash ').replace('_', '\_')


def compile_tex(rendered_tex, out_pdf_path):
    tmp_dir = tempfile.mkdtemp()
    in_tmp_path = os.path.join(tmp_dir, 'rendered.tex')
    with open(in_tmp_path, 'w') as outfile:
        outfile.write(rendered_tex)
    out_tmp_path = os.path.join(tmp_dir, 'rendered.tex')
    cwd = os.getcwd()
    os.chdir(out_pdf_path)
    latex_jinja_env.loader = jinja2.FileSystemLoader('./latex')
    for _ in range(2):
        p = Popen(['pdflatex', in_tmp_path, '-job-name',
                   'out', '-output-directory', tmp_dir])
        p.communicate()
    os.chdir(cwd)
    shutil.copy(out_tmp_path, out_pdf_path)
    shutil.rmtree(tmp_dir)
    clean_latex(out_pdf_path)
    return


def clean_latex(folder):
    for item in os.listdir(folder):
        if item.endswith(".aux") or item.endswith(".toc") or item.endswith(".log") or item.endswith(".out"):
            os.remove(os.path.join(folder, item))
    return


def make_reports(json_dir, doc, template_name='template.tex', out_dir='./reports'):
    # define processing function
    def _process_dict(model_dict):
        # rounding accuracies
        model_dict['training']['history']['val_accuracy_perc'] = str(round(
            100*float(model_dict['training']['history']['val_acc'][-1]), 2))
        model_dict['training']['history']['accuracy_perc'] = str(round(
            100*float(model_dict['training']['history']['acc'][-1]), 2))

        # correct in case of early stopping
        model_dict['training']['epochs'] = len(model_dict['training']['history']['loss'])

        # boolean to yes/no string
        model_dict['training']['shuffle'] = "Yes" if model_dict['training']['shuffle'] else "No"

        # add type to inbound layers
        layerno = 0
        for layer in model_dict['model']['layers']:
            layer['number'] = '' if layer['layertype']=='Activation' else layerno
            in_layers = layer['inbound_layers']
            layer['inbound_layers'] = []
            for k in range(len(in_layers)):
                in_layer = in_layers[k]
                layertype = [l['layertype'] for l in model_dict['model']
                             ['layers'] if l['name'] == in_layer][0]
                in_dict = {'name': in_layer.replace(
                    '_', '\_').strip(), 'layertype': layertype}
                layer['inbound_layers'].append(in_dict)
            layerno = layerno if layer['layertype']=='Activation' else layerno+1

        # layer names
        for layer in model_dict['model']['layers']:
            layer['name'] = layer['name'].replace('_', '\_').strip()

        # loss format
        model_dict['training']['loss'] = model_dict['training']['loss'].replace(
            '_', ' ')

        # model and dataset name
        model_dict['model']['name'] = str_to_latex(model_dict['model']['name'])

        # path
        weights_path = os.path.join(
            model_dict['model']['save_folder'], model_dict['model']['weights_filename'])
        if model_dict['model']['is_saved']:
            model_dict['model']['weights_path'] = str_to_latex(weights_path)
        else:
            model_dict['model']['weights_path'] = 'Weights not saved'

        # make optimizer config latex-friendly
        for key in model_dict['training']['optim_config'].keys():
            model_dict['training']['optim_config'] = str_to_latex(str(model_dict['training']['optim_config'][key]))

        # datetime
        timestamp = datetime.strptime(
            model_dict['metadata']['starttime'], model_dict['metadata']['timeformat_json'])
        model_dict['metadata']['starttime'] = datetime.strftime(
            timestamp, model_dict['metadata']['timeformat_pdf'])

        # device
        model_dict['metadata']['training_device']['device_string'] = "GPU (" + model_dict['metadata']['training_device']['device'] + \
            ")" if model_dict['metadata']['training_device']['gpu_used'] else "CPU"
        model_dict['metadata']['training_device']['cpu']['arch'] = str_to_latex(
            model_dict['metadata']['training_device']['cpu']['arch'])
        model_dict['metadata']['training_device']['cpu']['brand'] = str_to_latex(
            model_dict['metadata']['training_device']['cpu']['brand'])

        # plots
        model_dict['plots_tikz'] = get_tikz_strings(model_dict, do_hist=False)
        return model_dict

    # initialise list
    summaries = []

    count = 1
    for item in os.listdir(json_dir):
        # skip non json files
        if not item.endswith('.json'):
            print('SKIPPING file {}'.format(item))
            continue

        # import json file
        fullpath = os.path.join(json_dir, item)
        with open(fullpath, 'rb') as handle:
            model_dict = _process_dict(json.load(handle))
        model_dict['model']['reportnumber'] = count
        summaries.append(model_dict)
        count += 1

    # generate uniquified model list
    unique_modelnames = set([summary['model']['name']
                             for summary in summaries])
    unique_models = [{'modelname': modelname, 'model_idc': [k for k in range(len(
        summaries)) if modelname==summaries[k]['model']['name']]} for modelname in unique_modelnames]

    # generate pdf
    fn = 'template.tex'
    templ = latex_jinja_env.get_template(fn)
    rendered = templ.render(summaries=summaries, model_list=unique_models, doc=doc)
    compile_tex(rendered, out_dir)
    return summaries, unique_models


if __name__ == '__main__':
    # fn = 'template.tex'
    # templ=latex_jinja_env.get_template(fn)
    # model = {'name': 'UnetVanilla',
    #         'layers': ['xox', 'ly', 'nah']}
    # rendered = templ.render(model=model)
    # compile_tex(rendered, './reports')

    json_dir= r'D:\code_d\deep_training_reports\jsons'
    ms, un = make_reports(json_dir, doc={'title':'TITLE', 'author':'AUTHOR'})
