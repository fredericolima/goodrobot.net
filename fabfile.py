import os
import codecs
import re
import shutil

from fabric.api import task, local, run, cd, lcd
from fabric.colors import blue, green

from jinja2 import Environment, FileSystemLoader
from jinja2.exceptions import TemplateNotFound

import yaml
import mistune
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter


@task
def publish():
    with cd('./goodrobot.net'):
        run('git pull origin master')
        run('fab generate_all')


@task
def watch():
    print green('Watching ./src for changes')
    local('watchmedo shell-command -p "./src/*" -R -c "fab generate"')

@task
def deploy():
    generate_all()
    link_site('/srv/http/goodrobot')

@task
def generate_all():
    generate()
    print blue('Generating stream')
    stream()
    print blue('Generating pic stream')
    pic()


@task
def generate():
    print blue('Building folder structure')
    local('rm -rf ./build')
    build_dirs()
    print blue('Parsing templates')
    tpls()
    print blue('Parsing markdown')
    md()
    print blue('Generating css')
    css()


@task
def css():
    local('mkdir -p ./build/css')
    local('sassc ./src/_sass/gxl.sass ./build/css/gxl.css')


@task
def dev_build():
    print blue('Building folder structure')
    local('rm -rf ./build')
    build_dirs()
    print blue('Parsing templates')
    tpls()
    print blue('Parsing markdown')
    md()
    print blue('Generating stream')
    stream_cache()
    print blue('Generating pic stream')
    pic()


@task
def stream_cache():
    local('ankh src/stream/_stream.html build/stream/index.html --template-paths ./src --cache')


@task
def stream():
    local('ankh src/stream/_stream.html build/stream/index.html --template-paths ./src')


@task
def pic():
    local('ankh src/stream/_pic.html build/stream/pics.html --template-paths ./src')

@task
def link_site(destination='./test'):
    local('mkdir -p %s' % destination)
    local('rm -f %s/*' % destination)
    local('ln -sr ./build/* %s' % destination)
    with lcd(destination):
        local('ln -s ~/apps/gogs/public ./git')
        local('ln -s ~/apps/miu ./miu')
        local('ln -s ~/apps/goodrobot-ghost ./log')
        local('ln -s /srv/http/static ./static')


@task
def build_dirs():
    dir_list = ['build']
    file_list = []
    for subdir, dirs, files in os.walk('src'):
        if subdir.find(os.path.join('', '_')) == -1:
            build_dir = subdir.replace('src', 'build', 1)
            for dir in dirs:
                if dir.find('_') != 0:
                    dir_list.append(os.path.join(build_dir, dir))
            for file in files:
                if file.find('_') != 0:
                    file_list.append((
                        os.path.join(subdir, file),
                        os.path.join(build_dir, file)
                    ))

    for dir in dir_list:
        try:
            print "Creating %s" % dir
            os.mkdir(dir)
        except OSError:
            pass

    for src, dest in file_list:
        try:
            shutil.copyfile(src, dest)
        except:
            pass


@task
def tpls():
    tpls = []
    for subdir, dirs, files in os.walk('src'):
        build_dir = subdir.replace('src', 'build', 1)
        if subdir.find(os.path.join('', '_')) == -1:
            for file in files:
                if (file.find('_') != 0
                   and os.path.splitext(file)[1] == '.html'):
                    tpls.append((
                        os.path.join(subdir, file),
                        os.path.join(build_dir, file)
                    ))

    env = Environment(loader=FileSystemLoader(os.path.abspath('src')))
    for src, dest in tpls:

        print "Generating %s" % dest
        template = env.get_template(src.replace('src/', ''))
        html = template.render()

        destfile = codecs.open(dest, "w", "utf-8")
        destfile.write(html)
        destfile.close()


def strip_yaml(file_content):
    regex = re.compile('^---\n', re.MULTILINE)

    # if a yaml delimiter is the very first thing in the file grab it an
    # strip it out
    yaml_delimiters = regex.finditer(file_content)
    yaml_start = -1
    yaml_end = -1
    for d in yaml_delimiters:
        if yaml_start == -1:
            if d.start() == 0:
                yaml_start = 0
            else:
                break
        else:
            yaml_end = d.end()
            break

    if yaml_start != -1 and yaml_end != -1:
        yaml_src = file_content[yaml_start:yaml_end]
        yamls = yaml.load_all(yaml_src)
        template_vars = next(yamls)

        file_content = file_content.replace(yaml_src, '')
    else:
        template_vars = {}

    return file_content, template_vars


@task
def md():
    tpls = []
    for subdir, dirs, files in os.walk('src'):
        build_dir = subdir.replace('src', 'build', 1)
        if subdir.find(os.path.join('', '_')) == -1:
            for file in files:
                file_parts = os.path.splitext(file)
                if (file.find('_') != 0
                   and file_parts[1] == '.md'):
                    tpls.append((
                        os.path.join(subdir, file),
                        os.path.join(build_dir, '%s.html' % file_parts[0])
                    ))

    md = mistune.Markdown(renderer=Renderer())
    env = Environment(loader=FileSystemLoader(os.path.abspath('src')))

    try:
        template = env.get_template('_tpls/post.tpl')
    except TemplateNotFound:
        print "Could not find src/_tpls/post.tpl, has it been created?"
        return

    for src, dest in tpls:
        print "Generating %s" % dest
        with open(src, 'r') as content_file:
            content, template_vars = strip_yaml(content_file.read())

            markdown_html = md.render(content)
            template_vars['markdown'] = markdown_html

            html = template.render(template_vars)

            destfile = codecs.open(dest, "w", "utf-8")
            destfile.write(html)
            destfile.close()


class Renderer(mistune.Renderer):
    def block_code(self, code, lang):
        if not lang:
            return '\n<pre><code>%s</code></pre>\n' % \
                mistune.escape(code)
        lexer = get_lexer_by_name(lang, stripall=True)
        formatter = HtmlFormatter()
        return highlight(code, lexer, formatter)
