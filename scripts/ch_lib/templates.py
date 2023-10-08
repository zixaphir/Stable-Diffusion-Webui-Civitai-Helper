"""
HTML templates
"""

from string import Template
from . import util

article = Template(util.dedent("""
    <article style="margin: 5px; clear: both;">
        $thumbnail
        <div style="font-size:16px">
            File: $model_path
        </div>
        $download
        <div style="font-size:20px;margin:6px 0px;">
            <b>Model: <a href="$url" target="_blank"><u>$model_name</u></a></b>
        </div>
    </article>
""").strip())

thumbnail = Template(util.dedent("""
    <img src='$img_url' style='float: left; margin: 5px;'>
""").strip())

description = Template(util.dedent("""
    <blockquote style="font-size:16px;margin:6px 0px;">
        $description
    </blockquote>
    <br>
""").strip())

# add js function to download new version into SD webui by python
# in embed HTML, onclick= will also follow a ", never a ',
# so have to write it as following
download = Template(util.dedent("""
    <div style="font-size:16px;margin:6px 0px;">
        New Version: <u><a href="$download_url" target="_blank" style="margin:0px 10px;">$new_version_name</a></u>
        <u><a href='#' style='margin:0px 10px;' onclick="ch_dl_model_new_version(event, '$model_path', '$new_version_id', '$download_url', '$model_type')">[Download into SD]</a></u>
    </div>
""").strip())

no_download = Template(util.dedent("""
    <div style="font-size:16px;margin:6px 0px;">
        New Version: $new_version_name
    </div>
""").strip())
