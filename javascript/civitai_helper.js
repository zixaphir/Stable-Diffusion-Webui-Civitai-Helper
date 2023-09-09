"use strict";


function ch_convert_file_path_to_url(path){
    let prefix = "file=";
    let path_to_url = path.replaceAll('\\', '/');
    return prefix+path_to_url;
}

function ch_img_node_str(path){
    return `<img src='${ch_convert_file_path_to_url(path)}' style="width:24px"/>`;
}


function ch_gradio_version(){
    let foot = gradioApp().getElementById("footer");
    if (!foot){return null;}

    let versions = foot.querySelector(".versions");
    if (!versions){return null;}

    if (versions.textContent.indexOf("gradio: 3.16.2")>0) {
        return "3.16.2";
    } else {
        return "3.23.0";
    }

}


// send msg to python side by filling a hidden text box
// then will click a button to trigger an action
// msg is an object, not a string, will be stringify in this function
function send_ch_py_msg(msg){
    console.log("run send_ch_py_msg");
    let js_msg_txtbox = gradioApp().querySelector("#ch_js_msg_txtbox textarea");
    if (js_msg_txtbox && msg) {
        // fill to msg box
        js_msg_txtbox.value = JSON.stringify(msg);
        js_msg_txtbox.dispatchEvent(new Event("input"));
    }

}

// get msg from python side from a hidden textbox
// normally this is an old msg, need to wait for a new msg
function get_ch_py_msg(){
    console.log("run get_ch_py_msg");
    const py_msg_txtbox = gradioApp().querySelector("#ch_py_msg_txtbox textarea");
    if (py_msg_txtbox && py_msg_txtbox.value) {
        console.log("find py_msg_txtbox");
        console.log("py_msg_txtbox value: ");
        console.log(py_msg_txtbox.value);
        return py_msg_txtbox.value;
    } else {
        return "";
    }
}


// get msg from python side from a hidden textbox
// it will try once in every sencond, until it reach the max try times
const get_new_ch_py_msg = (max_count=3) => new Promise((resolve, reject) => {
    console.log("run get_new_ch_py_msg");

    let count = 0;
    let new_msg = "";
    let find_msg = false;
    const interval = setInterval(() => {
        const py_msg_txtbox = gradioApp().querySelector("#ch_py_msg_txtbox textarea");
        count++;

        if (py_msg_txtbox && py_msg_txtbox.value) {
            console.log("find py_msg_txtbox");
            console.log("py_msg_txtbox value: ");
            console.log(py_msg_txtbox.value);

            new_msg = py_msg_txtbox.value;
            if (new_msg != "") {
                find_msg = true;
            }
        }

        if (find_msg) {
            //clear msg in both sides
            py_msg_txtbox.value = "";
            py_msg_txtbox.dispatchEvent(new Event("input"));

            resolve(new_msg);
            clearInterval(interval);
        } else if (count > max_count) {
            //clear msg in both sides
            py_msg_txtbox.value = "";
            py_msg_txtbox.dispatchEvent(new Event("input"));

            reject('');
            clearInterval(interval);
        }

    }, 1000);
});


function getActiveTabType() {
    const currentTab = get_uiCurrentTabContent();
    switch (currentTab.id) {
        case "tab_txt2img":
            return "txt2img";
        case "tab_img2img":
            return "img2img";
    }
    return null;
}

function getExtraTabs(prefix) {
    return gradioApp().getElementById(prefix + "_extra_tabs");
}

function getActivePrompt() {
    const currentTab = get_uiCurrentTabContent();
    switch (currentTab.id) {
        case "tab_txt2img":
            return currentTab.querySelector("#txt2img_prompt textarea");
        case "tab_img2img":
            return currentTab.querySelector("#img2img_prompt textarea");
    }
    return null;
}

function getActiveNegativePrompt() {
    const currentTab = get_uiCurrentTabContent();
    switch (currentTab.id) {
        case "tab_txt2img":
            return currentTab.querySelector("#txt2img_neg_prompt textarea");
        case "tab_img2img":
            return currentTab.querySelector("#img2img_neg_prompt textarea");
    }
    return null;
}


//button's click function
async function open_model_url(event, model_type, search_term){
    console.log("start open_model_url");

    //get hidden components of extension
    let js_open_url_btn = gradioApp().getElementById("ch_js_open_url_btn");
    if (!js_open_url_btn) {
        console.log("Failed to find js_open_url_btn");
        return;
    }


    //msg to python side
    let msg = {
        "action": "",
        "model_type": "",
        "search_term": "",
        "prompt": "",
        "neg_prompt": "",
    };


    msg["action"] = "open_url";
    msg["model_type"] = model_type;
    msg["search_term"] = search_term;
    msg["prompt"] = "";
    msg["neg_prompt"] = "";

    // fill to msg box
    send_ch_py_msg(msg);

    //click hidden button
    js_open_url_btn.click();

    // stop parent event
    event.stopPropagation();
    event.preventDefault();

    //check response msg from python
    let new_py_msg = await get_new_ch_py_msg();
    console.log("new_py_msg:");
    console.log(new_py_msg);

    //check msg
    if (new_py_msg) {
        let py_msg_json = JSON.parse(new_py_msg);
        //check for url
        if (py_msg_json && py_msg_json.content) {
            if (py_msg_json.content.url) {
                window.open(py_msg_json.content.url, "_blank");
            }

        }


    }


    console.log("end open_model_url");


}

function add_trigger_words(event, model_type, search_term){
    console.log("start add_trigger_words");

    //get hidden components of extension
    let js_add_trigger_words_btn = gradioApp().getElementById("ch_js_add_trigger_words_btn");
    if (!js_add_trigger_words_btn) {
        return;
    }


    //msg to python side
    let msg = {
        "action": "",
        "model_type": "",
        "search_term": "",
        "prompt": "",
        "neg_prompt": "",
    };

    msg["action"] = "add_trigger_words";
    msg["model_type"] = model_type;
    msg["search_term"] = search_term;
    msg["neg_prompt"] = "";

    // get active prompt
    let act_prompt = getActivePrompt();
    msg["prompt"] = act_prompt.value;

    // fill to msg box
    send_ch_py_msg(msg);

    //click hidden button
    js_add_trigger_words_btn.click();

    console.log("end add_trigger_words");

    event.stopPropagation();
    event.preventDefault();


}

function use_preview_prompt(event, model_type, search_term){
    console.log("start use_preview_prompt");

    //get hidden components of extension
    let js_use_preview_prompt_btn = gradioApp().getElementById("ch_js_use_preview_prompt_btn");
    if (!js_use_preview_prompt_btn) {
        return;
    }

    //msg to python side
    let msg = {
        "action": "",
        "model_type": "",
        "search_term": "",
        "prompt": "",
        "neg_prompt": "",
    };

    msg["action"] = "use_preview_prompt";
    msg["model_type"] = model_type;
    msg["search_term"] = search_term;

    // get active prompt
    let act_prompt = getActivePrompt();
    msg["prompt"] = act_prompt.value;

    // get active neg prompt
    let neg_prompt = getActiveNegativePrompt();
    msg["neg_prompt"] = neg_prompt.value;

    // fill to msg box
    send_ch_py_msg(msg);

    //click hidden button
    js_use_preview_prompt_btn.click();

    console.log("end use_preview_prompt");

    event.stopPropagation();
    event.preventDefault();

}



// download model's new version into SD at python side
function ch_dl_model_new_version(event, model_path, version_id, download_url){
    console.log("start ch_dl_model_new_version");

    // must confirm before downloading
    let dl_confirm = "\nConfirm to download.\n\nCheck Download Model Section's log and console log for detail.";
    if (!confirm(dl_confirm)) {
        return;
    }

    //get hidden components of extension
    let js_dl_model_new_version_btn = gradioApp().getElementById("ch_js_dl_model_new_version_btn");
    if (!js_dl_model_new_version_btn) {
        return;
    }

    //msg to python side
    let msg = {
        "action": "",
        "model_path": "",
        "version_id": "",
        "download_url": "",
    };

    msg["action"] = "dl_model_new_version";
    msg["model_path"] = model_path;
    msg["version_id"] = version_id;
    msg["download_url"] = download_url;

    // fill to msg box
    send_ch_py_msg(msg);

    //click hidden button
    js_dl_model_new_version_btn.click();

    console.log("end dl_model_new_version");

    event.stopPropagation();
    event.preventDefault();


}

function processCards(tab, extra_tab_els) {
    const prefix_length = tab.length + 1;
    for (const el of extra_tab_els) {
        const model_type = el.id.slice(prefix_length, -6);
        const cards = el.querySelectorAll('.card');
        for (const card of cards) {
            processSingleCard(tab, getShortModelTypeFromFull(model_type), card);
        }
    }
}


function getModelCardsEl(prefix, model_type) {
    const id = prefix + "_" + model_type + "_cards";
    return gradioApp().getElementById(id);
}


function waitForExtraTabs(tab, extra_tabs) {
    function findTabs() {
        const tab_elements = [];
        for (const extra_tab of extra_tabs) {
            const id = tab + "_" + extra_tab + "_cards";
            const extra_tab_el = getModelCardsEl(tab, extra_tab);

            if (extra_tab_el == null) {

                // XXX lycoris models do not have their own tab in sdwebui 1.5
                // most of the time. In the case that there is a LyCoris tab,
                // it would have been added at the same time as the others,
                // making it almost impossible to be null by the time we're at
                // this point in the code if the other tabs are loaded.
                if (extra_tab == 'lycoris') { continue; }

                return null;
            }

            tab_elements.push(extra_tab_el);
        }
        return tab_elements;
    }

    const tab_elements = findTabs(tab, extra_tabs);
    if (tab_elements) {
        processCards(tab, tab_elements);
    }

    const observer = new MutationObserver(records => {
        let tab_elements;
        for (const record of records) {
            if (record.type != "childList") {
                continue;
            }

            tab_elements = findTabs(tab, extra_tabs);
            if (!tab_elements) {
                return;
            }

            processCards(tab, tab_elements);
            return;
        }
    });

    const extra_networks = getExtraTabs(tab);

    const options = {
        subtree: true,
        childList: true,
    };

    observer.observe(extra_networks, options);

}


function waitForEditor(page, type, name) {
    const id = page + '_' + type + '_edit_user_metadata';

    return new Promise(resolve => {
        let name_field;
        const gradio = gradioApp();

        const editor = gradio.getElementById(id);
        const popup = gradio.querySelector(".global-popup");

        if (popup != null) {
            // hide the editor window so it doesn't get in the user's
            // way while we wait for the replace preview functionality
            // to become available.
            popup.style.display = "none";
        }

        // not only do we need to wait for the editor,
        // but also for it to populate with the model metadata.
        if (editor != null) {
            name_field = editor.querySelector('.extra-network-name');
            if (name_field.textContent.trim() == name) {
                return resolve(editor);
            }
        }

        const observer = new MutationObserver(() => {
            const editor = gradioApp().getElementById(id);
            let name_field;
            if (editor != null) {
                name_field = editor.querySelector('.extra-network-name');
                if (name_field.textContent.trim() == name) {
                    resolve(editor);
                    observer.disconnect();
                }
            }
        });

        observer.observe(document.body, {
            subtree: true,
            childList: true,
        });
    });
}


function getShortModelTypeFromFull(model_type_full) {
    switch (model_type_full) {
        case "textual_inversion":
            return "ti";
        case "hypernetworks":
            return "hyper";
        case "checkpoints":
            return "ckp";
        case "lora":
        case "lycoris":
            return model_type_full;
    }
}


function getLongModelTypeFromShort(model_type_short) {
    switch (model_type_short) {
        case "ti":
            return "textual_inversion";
        case "hyper":
            return "hypernetworks";
        case "ckp":
            return "checkpoints";
        case "lora":
        case "lycoris":
            return model_type_short;
    }
}


function isThumbMode(extra_network_node) {
    if (extra_network_node?.className == "extra-network-thumbs") {
        return true;
    }
    return false;
}


function processSingleCard(active_tab_type, active_extra_tab_type, card) {
    let metadata_button = null;
    let additional_node = null;
    let replace_preview_btn = null;
    let ul_node = null;
    let search_term_node = null;
    let search_term = "";
    let model_type = active_extra_tab_type;
    let js_model_type = getLongModelTypeFromShort(model_type);

    //css
    let btn_margin = "0px 5px";
    let btn_fontSize = "200%";
    let btn_thumb_fontSize = "100%";
    let btn_thumb_display = "inline";
    let btn_thumb_pos = "static";
    let btn_thumb_backgroundImage = "none";
    let btn_thumb_background = "rgba(0, 0, 0, 0.8)";

    let is_thumb_mode = isThumbMode(getModelCardsEl(active_tab_type, js_model_type));

    //metadata_buttoncard
    metadata_button = card.querySelector(".metadata-button");
    //additional node
    additional_node = card.querySelector(".actions .additional");
    //get ul node, which is the parent of all buttons
    ul_node = card.querySelector(".actions .additional ul");
    // replace preview text button
    replace_preview_btn = card.querySelector(".actions .additional a");

    if (replace_preview_btn == null) {
        /*
        * in sdwebui 1.5, the replace preview button has been
        * moved to a hard to reach location, so we have to do
        * quite a lot to get to its functionality.
        */

        // waste memory by keeping all of this in scope, per card.
        let page = active_tab_type;
        let type = js_model_type;
        let name = card.dataset.name;

        // create the replace_preview_btn, as it no longer exists
        replace_preview_btn = document.createElement("a");

        // create an event handler to redirect a click to the real replace_preview_button
        replace_preview_btn.addEventListener("click", function(e) {
            // we have to create a whole hidden editor window to access preview replace functionality
            extraNetworksEditUserMetadata(e, page, type, name);

            // the editor window takes quite some time to populate. What a waste.
            waitForEditor(page, type, name).then(editor => {
                // Gather the buttons we need to both replace the preview and close the editor
                let cancel_button = editor.querySelector('.edit-user-metadata-buttons button:first-of-type');
                let replace_preview_button = editor.querySelector('.edit-user-metadata-buttons button:nth-of-type(2)');

                replace_preview_button.click();
                cancel_button.click();
            });
        });
    }

    // check thumb mode
    if (is_thumb_mode) {
        additional_node.style.display = null;

        if (!ul_node) {
            // nothing to do.
            return;
        }

        if (opts["ch_show_btn_on_thumb"]) {
            ul_node.style.background = btn_thumb_background;
        } else {
            let ch_btn_txts = ['🌐', '💡', '🏷️'];

            // remove existed buttons
            //reset
            ul_node.style.background = null;
            // find all .a child nodes
            let atags = ul_node.querySelectorAll("a");

            for (let atag of atags) {
                //reset display
                atag.style.display = null;
                //remove extension's button
                if (ch_btn_txts.indexOf(atag.textContent)>=0) {
                    //need to remove
                    ul_node.removeChild(atag);
                } else {
                    //do not remove, just reset
                    atag.textContent = replace_preview_text;
                    atag.style.display = null;
                    atag.style.fontSize = null;
                    atag.style.position = null;
                    atag.style.backgroundImage = null;
                }
            }

            //also remove br tag in ul
            let brtag = ul_node.querySelector("br");
            if (brtag) {
                ul_node.removeChild(brtag);
            }

            //just reset and remove nodes, do nothing else
            return;

        }

    } else {
        // full preview mode

        if (opts.ch_always_display) {
            additional_node.style.display = "block";
        } else {
            additional_node.style.display = null;
        }

        if (!ul_node) {
            ul_node = document.createElement("ul");
        } else {
            // remove br tag
            let brtag = ul_node.querySelector("br");
            if (brtag) {
                ul_node.removeChild(brtag);
            }
        }

    }

    if (replace_preview_btn) {
        // change replace preview text button into icon
        if (replace_preview_btn.textContent !== "🖼️") {
            ul_node.appendChild(replace_preview_btn);
            replace_preview_btn.textContent = "🖼️";
            if (!is_thumb_mode) {
                replace_preview_btn.style.fontSize = btn_fontSize;
                replace_preview_btn.style.margin = btn_margin;
            } else {
                replace_preview_btn.style.display = btn_thumb_display;
                replace_preview_btn.style.fontSize = btn_thumb_fontSize;
                replace_preview_btn.style.position = btn_thumb_pos;
                replace_preview_btn.style.backgroundImage = btn_thumb_backgroundImage;
            }

        }
    }

    if (ul_node.querySelector('.openurl')) {
        return;
    }

    // search_term node
    // search_term = subfolder path + model name + ext
    search_term_node = card.querySelector(".actions .additional .search_term");
    if (!search_term_node){
        console.log("can not find search_term node for cards in " + active_tab_type + "_" + active_extra_tab_type + "_cards");
        return;
    }

    // get search_term
    search_term = search_term_node.textContent;
    if (!search_term) {
        console.log("search_term is empty for cards in " + active_tab_type + "_" + active_extra_tab_type + "_cards");
        return;
    }

    // then we need to add 3 buttons to each ul node:
    let open_url_node = document.createElement("a");
    open_url_node.href = "#";
    open_url_node.textContent = "🌐";
    open_url_node.className = "openurl";
    if (!is_thumb_mode) {
        open_url_node.style.fontSize = btn_fontSize;
        open_url_node.style.margin = btn_margin;
    } else {
        open_url_node.style.display = btn_thumb_display;
        open_url_node.style.fontSize = btn_thumb_fontSize;
        open_url_node.style.position = btn_thumb_pos;
        open_url_node.style.backgroundImage = btn_thumb_backgroundImage;
    }
    open_url_node.title = "Open this model's civitai url";
    open_url_node.setAttribute("onclick","open_model_url(event, '" + model_type + "', '" + search_term + "')");

    let add_trigger_words_node = document.createElement("a");
    add_trigger_words_node.href = "#";
    add_trigger_words_node.textContent = "💡";
    add_trigger_words_node.className = "addtriggerwords";
    if (!is_thumb_mode) {
        add_trigger_words_node.style.fontSize = btn_fontSize;
        add_trigger_words_node.style.margin = btn_margin;
    } else {
        add_trigger_words_node.style.display = btn_thumb_display;
        add_trigger_words_node.style.fontSize = btn_thumb_fontSize;
        add_trigger_words_node.style.position = btn_thumb_pos;
        add_trigger_words_node.style.backgroundImage = btn_thumb_backgroundImage;
    }

    add_trigger_words_node.title = "Add trigger words to prompt";
    add_trigger_words_node.setAttribute("onclick","add_trigger_words(event, '" + model_type + "', '" + search_term + "')");

    let use_preview_prompt_node = document.createElement("a");
    use_preview_prompt_node.href = "#";
    use_preview_prompt_node.textContent = "🏷️";
    use_preview_prompt_node.className = "usepreviewprompt";
    if (!is_thumb_mode) {
        use_preview_prompt_node.style.fontSize = btn_fontSize;
        use_preview_prompt_node.style.margin = btn_margin;
    } else {
        use_preview_prompt_node.style.display = btn_thumb_display;
        use_preview_prompt_node.style.fontSize = btn_thumb_fontSize;
        use_preview_prompt_node.style.position = btn_thumb_pos;
        use_preview_prompt_node.style.backgroundImage = btn_thumb_backgroundImage;
    }
    use_preview_prompt_node.title = "Use prompt from preview image";
    use_preview_prompt_node.setAttribute("onclick","use_preview_prompt(event, '" + model_type + "', '" + search_term + "')");

    //add to card
    ul_node.appendChild(open_url_node);
    //add br if metadata_button exists
    if (is_thumb_mode && metadata_button) {
        ul_node.appendChild(document.createElement("br"));
    }
    ul_node.appendChild(add_trigger_words_node);
    ul_node.appendChild(use_preview_prompt_node);

    if (!ul_node.parentElement) {
        additional_node.appendChild(ul_node);
    }

}

onUiLoaded(() => {

    //get gradio version
    const gradio_ver = ch_gradio_version();
    console.log("Running Stable-Diffusion-Webui-Civitai-Helper on Gradio Version: " + gradio_ver);

    // get all extra network tabs
    const tab_prefix_list = ["txt2img", "img2img"];
    const model_type_list = ["textual_inversion", "hypernetworks", "checkpoints", "lora", "lycoris"];

    // update extra network tab pages' cards
    // * replace "replace preview" text button into an icon
    // * add 3 button to each card:
    //  - open model url 🌐
    //  - add trigger words 💡
    //  - use preview image's prompt 🏷️
    // notice: javascript can not get response from python side
    // so, these buttons just sent request to python
    // then, python side gonna open url and update prompt text box, without telling js side.
    function update_card_for_civitai() {

        let replace_preview_text = getTranslation("replace preview");
        if (!replace_preview_text) {
            replace_preview_text = "replace preview";
        }

        let extra_network_id = "";
        let extra_network_node = null;
        let model_type = "";
        let cards = null;
        let is_thumb_mode = false;

        //get current tab
        let active_tab_type = getActiveTabType();
        if (!active_tab_type) {active_tab_type = "txt2img";}

        for (const tab_prefix of tab_prefix_list) {
            if (tab_prefix != active_tab_type) {continue;}

            //find out current selected model type tab
            const extra_tabs = getExtraTabs(tab_prefix);

            //get active extratab
            const re = new RegExp(tab_prefix + "_(.+)_cards");
            const active_extra_tab = Array.from(get_uiCurrentTabContent().querySelectorAll('.extra-network-cards,.extra-network-thumbs'))
                .find(el => el.closest('.tabitem').style.display === 'block')
                ?.id.match(re)[1];

            const active_extra_tab_type = getShortModelTypeFromFull(active_extra_tab);

            for (const js_model_type of model_type_list) {
                //get model_type for python side
                model_type = getShortModelTypeFromFull(js_model_type);

                if (!model_type) {
                    console.log("can not get model_type from: " + js_model_type);
                    continue;
                }


                //only handle current sub-tab
                if (model_type != active_extra_tab_type) {
                    continue;
                }

                //console.log("handle active extra tab");
                extra_network_id = tab_prefix + "_" + js_model_type + "_cards";

                // console.log("searching extra_network_node: " + extra_network_id);
                extra_network_node = getModelCardsEl(tab_prefix, js_model_type);

                // check if extra network is under thumbnail mode
                // XXX thumbnail mode removed in sd-webui v1.5.0
                is_thumb_mode = isThumbMode(extra_network_node);

                // get all card nodes
                cards = extra_network_node.querySelectorAll(".card");
                for (const card of cards) {
                    processSingleCard(active_tab_type, active_extra_tab_type, card);
                }

            }

        }

    }

    /*
    let extra_network_refresh_btn = null;
    */
    let extra_networks_btn = null;

    //add refresh button to extra network's toolbar
    for (const prefix of tab_prefix_list) {
        // load extra networks button
        extra_networks_btn = gradioApp().getElementById(prefix + "_extra_networks");


        // pre-1.6
        if (extra_networks_btn) {
            function extraNetworksClick(e) {
                waitForExtraTabs(prefix, model_type_list);
                extra_networks_btn.removeEventListener("click", extraNetworksClick);
            }

            // add listener to extra_networks_btn
            extra_networks_btn.addEventListener('click', extraNetworksClick);
            continue;

        }

        // 1.6 and higher
        const extra_tab = getExtraTabs(prefix);
        const headers = extra_tab.firstChild.children;

        for (const header of headers) {
            const model_type = header.textContent.trim().replace(" ", "_").toLowerCase();

            function extraNetworksClick(e) {
                waitForExtraTabs(prefix, [model_type]);
                header.removeEventListener("click", extraNetworksClick);
            }

            header.addEventListener('click', extraNetworksClick);
        }

        //get toolbar
        extra_networks_btn = gradioApp().getElementById(prefix + "_extra_networks");

        function extraNetworksClick(e) {
            waitForExtraTabs(prefix, model_type_list);
            extra_networks_btn.removeEventListener("click", extraNetworksClick);
        }

    }

    //run it once
    update_card_for_civitai();


});



