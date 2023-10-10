**[Contributors](https://github.com/zixaphir/Stable-Diffusion-Webui-Civitai-Helper/graphs/contributors)**

### Language
[中文(ChatGPT)](README.cn.md)
[日本語(ChatGPT)](README.jp.md)
[한국어(ChatGPT)](README.kr.md)

## About Civitai Helper
This extension provides the ability to download models and model metadata from Civitai. Data such as activation keywords, model description, version information, and model previews for models hosted on Civitai can be at your fingertips without having to navigate away from stable diffusion webui.

## About This Version of Civitai Helper
This is my personal version of Stable-Diffusion-Webui-Civitai-Helper. I started it entirely because the version I was using broke when SD-webui v1.5 came out and I needed it to work. Since then, I have added functionality that I wanted and have made best-effort attempts to maintain compatibility with older versions of sd-webui, but I do not use older versions and therefore do not test on older versions.

I intend to keep this working for as long as I am able, but this is simply a hobby project and I am nowhere near as skilled as other extension developers with more experience. I am likely to dip out for long periods at a time, possibly forever if I lose interest. I am prone to errors and bugs are to be expected.

If a more interested part decides to pick up development, I will happily cede control of this project and attempt to push my changes to their projects if they are wanted.

# Civitai Helper
Stable Diffusion Webui Extension for Civitai, to handle your models much more easily.

Civitai: ![Civitai Url](https://civitai.com/models/16768/civitai-helper-sd-webui-civitai-extension)

# Features
* Scans all models to download model information and preview images from Civitai.
* Link local model to a civitai model by civitai model's url
* Download a model(with info+preview) by Civitai Url into SD's model folder or subfolder.
* Downloading can resume at break-point, which is good for large file.
* Checking all your local model's new version from Civitai
* Download a new version directly into SD model folder (with info+preview)
* Modified Built-in "Extra Network" cards, to add the following buttons on each card:
  - 🖼️: Modified "replace preview" text into this icon
  - 🌐: Open this model's Civitai url in a new tab
  - 💡: Add this model's trigger words to prompt
  - 🏷️: Use this model's preview image's prompt
  - ✏️: Rename model
  - ❌: Remove/Delete model
* Above buttons support thumbnail mode of Extra Network in versions of webui prior to 1.5.0.
    * Thumbnail mode was removed in v1.5.0 of webui and replaced customizable model card sizes.
* Option to always show additional buttons, to work with touchscreen.
* To the best of my knowledge, this extension should still work in versions of webui prior to v1.5.0, but it is not tested. I make best-effort attempts to write code that *should* maintain compatibility with older versions, but if you have run into problems, please file an issue and I'll attempt to resolve it.

# Install
Go to SD webui's extension tab, go to `Install from url` sub-tab.
Copy this project's url into it, click install.

Alternatively, download this project as a zip file, and unzip it to `Your SD webui folder/extensions`.

Everytime you install or update this extension, you need to shutdown SD Webui and Relaunch it. Just "Reload UI" won't work for this extension.

Done.

## Branches
Development of this extension happens in three development branches:
* **`master`**: The current version of the extension intended for end users. Out-of-version changes to this branch only exist to hotfix critical issues found after the release of a new version.
* **`dev`**: The active development version of this extension. This will always have the most up-to-date changes but is also the most likely to contain bugs
* **`v1.6ONLY`**: Not supported and not really intended for anybody except for me. Slowest to update and less tested than other branches, this branch only runs on the latest version of webui. Compatibility code for older versions is actively removed, and whether I'm running it on webui stable or webui dev is in flux. In theory, this is the most optimized version of the extension, but it's often just me chasing waterfalls. Do not submit issues if you use this branch. They will be marked as invalid, closed, and otherwise ignored.

## Update Your SD Webui
This extension need to get extra network's cards id. Which is added since **2023-02-06**.
**If your SD webui is an earlier version, you need to update it!**

### Some of the following information may not up-to-date. Most functionality should be the same or similar, but many changes post-v1.6 have not been documented as of yet. Images may not match 1:1 with the current state of the extension.

## Scanning Models
Go to extension tab "Civitai Helper". There is a button called "Scan model".

![](img/extension_tab.jpg)

Click it and the extension will scan all your models to generate SHA256 hashes, using them to retreive model information and preview images from Civitai.

**Scanning takes time, just wait it finish**

For each model, it will create two files to save all model info from Civitai. These model info files will be `[model_name].civitai.info` and `[model_name].json` in your model folder.

![](img/model_info_file.jpg)

If a model info file already exists, by default it will be skipped. If a model cannot be found in Civitai, a minimal model info file will be created with any information that can be extracted from the model. By default, a model with model pre-existing model info files will not be scanned.

### Adding New Models
When you have some new models, just click scan button again to get new model's information and preview images. Only new models will be scanned with default options.

## Model Card

### The following section is outdated!
The following text block and image only applies to Stable Diffution Webui versions before v1.5.0. While the added buttons are still up-to-date, the "Extra Networks" tab button has been removed and is now always active by default.

---

**(Use this only after scanning finished)**
Open SD webui's build-in "Extra Network" tab, to show model cards.

![](img/extra_network.jpg)


Move your mouse on to the bottom of a model card. It will show 4 icon buttons:
  - 🖼: Replace preview (a build-in button, modified from text to icon)
  - 🌐: Open this model's Civitai url in a new tab
  - 💡: Add this model's trigger words to prompt
  - 🏷: Use this model's preview image's prompt
  - ✏️: Rename model
  - ❌: Remove/Delete model

![](img/model_card.jpg)

## Webui Metadata Editor
As of v1.7.0, this extension also downloads data for Webui's Metadata Editor by default. This data includes information you'd previously have to read unruly JSON files or navigate to Civitai to read.

![](img/webui_metadata_editor.png)

This data can be accessed by clicking the metadata button on the model card.

![](img/webui_metadata_button.png)

## Download
To download a model by Civitai Model Page's Url, you need 3 steps:
* Fill the Civitai URL or Model ID
* Click "1. Get Model Information by Civitai Url.
* It will fill model name, type, sub-folder, and model version automatically, but you can change the sub-folder and model version if you need to.
  * If you need to add more sub-folders, you must do this by navigating to the model directory on the system running your webui version.
* Click download.

![](img/download_model.jpg)

Detail will be displayed on console log, with a progress bar.
Downloading can resume from break-point, so no fear for large file.

## Checking Model's New Version
You can checking your local model's new version from civitai by model types. You can select multiple model types.

![](img/check_model_new_version.jpg)

The checking process has a small delay after each model's new version checking request. So it is a little slow.

This is to protect Civitai from issue like DDos from this extension. There is no good for us if it is down.

**After checking process done**, it will display all new version's information on UI.

There are 3 urls for each new version.
* First one is model's civitai page.
* Second one is new version's download url.
* Third one is a button to download it into your SD's model folder with python.
With this one, output information is on "Download Model" section's log and console log. **One task at a time**.

![](img/check_model_new_version_output.png)

## Get Model Info By Url
This is used to force a local model links to a Civitai model. For example, you converted a model's format or pruned it. Then it can not be found on civitai when scanning.

In that case, if you still want to link it to a civitai model. You can use this funcion.

Choose this model from list, then offer a civitai model page's url.

After clicking button, extension will download that civitai model's info and preview image for the local file you picked.

![](img/get_one_model_info.jpg)

## Proxy
**If you are updating to new version, you need to re-lanuch SD webui before using it.**

Proxy textbox is at the bottom of extension tab.

**Each time you fill or clear a proxy value, you need to save setting, and Re-load UI with setting tab's reload button.**

Then all requests to civitai will use the proxy.

For some sock5 proxy, need to be used as "socks5h://xxxxx".

## Other Setting
**The Save Setting button, will save both "Scan Model"'s setting and other setting.**

* "Always Display Button" is good for touch screen.
* "Show Buttons on Thumb Mode" will turn on/off additional Buttons on thumbnail.
    * Thumbnail Mode was removed in v1.5.0 of webui.

![](img/other_setting.jpg)

## Preview Image
Extra network uses both `model_file.png` and `model_file.preview.png` as preview image. But `model_file.png` has higher priority, because it is created by yourself.

When you don't have the higher priority one, it will use the other automatically.

## Prompt
When you click the button "Use prompt from preview image", it does not use the prompt from your own preview image. It uses the one from civitai's preview image.

On civitai, a model's preview images may not has prompt. This extension will check this model's all civitai preview images' information and use the first one has prompt in it.

## SHA256
To create a file SHA256, it need to read the whole file to generate a hash code. It gonna be slow for large files.

Also, extension uses Memory Optimized SHA256, which won't stuck your system and works with colab.

There are 2 cases this hash code can not find the model on civitai:
* Some old models, which do not have SHA256 code on civitai.
* The model's owner changed file on civitai, but does not change version name and description. So, the file on civitai is actually not the one on your manchine.

In these cases, you can always link a model to civitai by filling its URL in this extension.

## Feature Request
Feel free to submit feature requests, but pull requests are preferred.

Enjoy!

## Pull Requests
All pull requests should target the dev branch. For those who take a stab at the code, I apologize for the lack of consistency in coding style, naming, and other syntactical oddities. At some point, I intend to clean up the code and have everything pass linting, but we're not there yet.

## Common Issue
### 4 Buttons on card didn't show
#### Localization
There was a Localization issue if you are not using English version of SD webui. This is fixed in the latest version of this extension. **Bilingual localization extension is supported by PR since v1.6.1.1.**

##### Using cloud based localization extension
Turn off cloud based localization extension, use normal localization extension.

#### Other case
First of all, make sure you clicked "Refresh Civitai Helper" button.

If issue is still there, then only reason is you are not using the latest SD webui. So, Make sure you updated it.

Your update could be failed if you have modified SD webui's file. You need to check git command's console log to make sure it is updated.

In many cases, git will just refuse to update and tell you there are some conflicts need you to handle manually. If you don't check the consloe log, you will think your SD webui is updated, but it is not.

### Request, Scan or Get model info failed
Usually the reason for this most likely is the connection to Civitai API service failed. This can be for a number of reasons.

Sometimes Civitai can be down or refuse your API connection. Civitai has a connection pool setting. Basicly, it's a max connection number that civitai can have at the same time. So if there are already too manny connections on civitai, it will refuse your API connection.

In those cases, the only thing you can do is just wait a while then try again. I suggest making a cup of tea!

### Get Wrong model info and preview images from civitai
A bad news is, some models are saved with a wrong sha256 in civitai's database. Check here for more detail:
[https://github.com/civitai/civitai/issues/426](https://github.com/civitai/civitai/issues/426)

So, for those models, this extension can not get the right model info or preview images.

In this case, you have to remove the model info file and get the right model info by a civitai url on this extension's tab page.

Also, you can report those models with wrong sha256 to civitai at following page:
[https://discord.com/channels/1037799583784370196/1096271712959615100/1096271712959615100](https://discord.com/channels/1037799583784370196/1096271712959615100/1096271712959615100)

Please report that model to civitai, so they can fix it.

### Scanning fail when using colab
First of, search your error message with google. Most likely, it will be a colab issue.

If you are sure it is a out of memory issue when scanning models, and you are using this extension's latest version, then there is nothing we can do.

Since v1.5.5, we've already optimized the SHA256 function to the top. So the only 2 choices for you are:
* try again
* or use a pro account of colab.

### (Changes)[https://github.com/zixaphir/Stable-Diffusion-Webui-Civitai-Helper/blob/master/README.md]
