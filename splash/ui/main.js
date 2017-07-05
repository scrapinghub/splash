(function(){

var splash = window.splash || {};
var params = splash.params || {};

if(splash.lua_enabled) {
    $(document.body).removeClass('no-lua').addClass('has-lua');

    var splash_commands = {};
    var splash_commands_names = [];
    var splash_property_names = [];
    // Load documentation for autocompletion
    $.getJSON('/_ui/inspections/splash-auto.json', function(data) {
        var pos = 'splash:'.length;
        for(var method in data) {
            (method[pos-1] == ':' ? splash_commands_names : splash_property_names).push(method.substring(pos));
            splash_commands[method.substring(pos)] = data[method];
        }
    });

    var CODEMIRROR_OPTIONS = {
        mode: 'lua',
        lineNumbers: true,
        autofocus: true,
        tabSize: 2,
        matchBrackets: false,  // doesn't look good in mbo theme
        autoCloseBrackets: true,
        extraKeys: {
            "Ctrl-Space": "autocomplete",
        },
        theme: 'mbo',
    };

    var $tooltip = $('<div class="splash-tooltip"></div>').appendTo(document.body).hide();
    var autocomplete = function autocomplete(cm) {
        var cur = cm.getCursor(), line = cm.getRange({line: cur.line, ch:0}, cur);
        var match = line.match(/splash([:\.])[a-z_]*$/);
        if (match) {
            var hints = CodeMirror.hint.fromList(cm, {
                words: match[1] == ':' ? splash_commands_names : splash_property_names
            });
            if(!hints) {
                return;
            }
            CodeMirror.on(hints, "close", function() { $tooltip.hide(); });
            CodeMirror.on(hints, "update", function() { $tooltip.hide(); });
            CodeMirror.on(hints, "select", function(cur, node) {
                var rect = node.parentNode.getBoundingClientRect();
                var left = (rect.right + window.pageXOffset) + 'px';
                var top = (rect.top + window.pageYOffset) + 'px';
                var docs = splash_commands[cur] && splash_commands[cur].short;
                if(docs){
                    $tooltip.html(docs).css({left: left, top: top}).show();
                } else {
                    $tooltip.hide();
                }
            });
            return hints;
        }
    };

    var init_editor = function init_editor(){
        if(splash.lua_enabled && !splash.editor) {
            /* Create editor */
            var textarea = $('#lua-code-editor');
            textarea.val(params.lua_source || splash.example_script || "");
            if (textarea.is(':visible')) {
                var editor = splash.editor = CodeMirror.fromTextArea(textarea[0], CODEMIRROR_OPTIONS);
                editor.setSize(464, 464);
                editor.on("keyup", function (cm, event) {
                    var kc = event.keyCode;
                    if (!cm.state.completionActive && ((kc >= 48 && kc <= 90) || kc === 190 || kc === 16)) { // a-z . and :
                        CodeMirror.commands.autocomplete(cm, null, {
                            completeSingle: false,
                            hint: autocomplete,
                        });
                    }
                });
            }
        }
    };

    $(document).ready(init_editor);
    $('#render-form').on("shown.bs.dropdown", init_editor);
    $('#lua-code-editor-panel').click(function(e){
        e.stopPropagation();
    });
}

splash.loadExample = function(name, exampleUrl) {
    $.get('/_ui/examples/' + encodeURI(name) + '.lua', function(code) {
        if(typeof exampleUrl === "string") {
            $('input[name="url"]').val(exampleUrl);
        }
        splash.editor.getDoc().setValue(code);
        var button = $('button[type="submit"]').tooltip({
            html: true,
            title: "Example code loaded!<br/>Now click here to run.",
            placement: "right"
        }).tooltip("show");
        $(document.body).one('click', function(){
            button.tooltip('destroy');
        });
    });
};

function loadHarViewer(har) {
    if(splash.harLoaded) {
        return $(); // Multiple har files in response, only show UI for the first one
    }
    splash.harLoaded = true;
    // Load HARViewer libraries
    var harPath = '_ui/' + splash.harviewer_path + '/scripts';
    $('<script data-main="' + harPath + '/harViewer" src="' + harPath + '/require.js"></script>').appendTo(document.body);

    var $container = $('<div/>')
        .addClass('indent').attr('id', 'content') // Id is hardcoded into harviewer
        .text('Loading HARViewer...');

    /* Initialize HAR viewer */
    $container.bind("onViewerPreInit", function(event){
        // Get application object
        var viewer = event.target.repObject;

        // Remove unnecessary/unsupported tabs
        viewer.removeTab("Home");
        viewer.removeTab("DOM");
        viewer.removeTab("About");
        viewer.removeTab("Schema");
        // Hide the tab bar
        viewer.showTabBar(false);

        // Remove toolbar buttons
        var preview = viewer.getTab("Preview");
        preview.toolbar.removeButton("download");
        preview.toolbar.removeButton("clear");
        preview.toolbar.removeButton("showTimeline");

        var events = [
            {name: "_onStarted", description: "Page processing is started"},
            {name: "_onPrepareStart", description: "Rendering begins"},
            {name: "_onFullViewportSet", description: "Viewport is changed to full"},
            {name: "_onCustomJsExecuted", description: "Custom JavaScript is executed"},
            {name: "_onScreenshotPrepared", description: "Screenshot is taken"},
            {name: "_onPngRendered", description: "Screenshot is encoded"},
            {name: "_onHtmlRendered", description: "HTML is rendered"},
            {name: "_onIframesRendered", description: "Iframes info is calculated"},
        ];

        for (var i=0; i<events.length; i++){
            var obj = events[i];
            obj.classes = "customEventBar " + obj.name;
            preview.addPageTiming(obj);
        }

        // Make sure stats are visible to the user by default
        preview.showStats(true);
    });

    $container.bind("onViewerInit", function(event){
        var viewer = event.target.repObject;
        viewer.appendPreview(har);
    });
    return $container;
}

function downloadButton(fileName, encoding, contents) {
    return $('<a/>').addClass('action').text('download')
        .attr('download', fileName)
        .attr('href', "data:" + encoding + "," + contents);
}

function renderString(s, $cnt) {
    // An string can be rendered as a simple string, as long string block or
    // as a base64-encoded image

    if(s.length < 120) { // Standalone simple string
        var encodedString = JSON.stringify([s]);
        encodedString = encodedString.substring(1, encodedString.length - 1);
        $cnt.addClass('string').text(encodedString);
        return;
    }
    // Block of text or image
    // Test if it can be loaded as a PNG or JPG image
    var rendered = false;
    var pending = 2;

    function try_load(ext) {
        var i = new Image();
        i.onload = function(){
            if(!rendered) {
                $cnt.append('<span class="type">Image</span> (' + ext + ', ' + i.width + 'x' + i.height + ')').append(
                    downloadButton(splash.pageName + '.' + ext, "image/" + ext + ";base64", s)
                ).append(
                    $('<div/>').addClass('indent').append(
                        $('<a/>').attr('href', "data:image/" + ext + ";base64," + s)
                        .attr('target', '_blank').append(
                            $(i).attr('title', 'Open in new tab').addClass('small')
                        )
                    )
                );
                rendered = true;
            }
        };
        i.onerror = function(){
            if(!rendered && --pending === 0) {
                rendered = true;
                $cnt.append('String (length ' + s.length + ')').append(
                    downloadButton(splash.pageName + '.txt', "text/plain;charset=utf-8", encodeURIComponent(s))
                ).append(
                    $('<div/>').addClass('indent').append(
                        $('<textarea rows="15"></textarea>').val(s)
                    )
                );
            }
        };
        i.src = "data:image/" + ext + ";base64," + s;
    }

    try_load('png');
    try_load('jpeg');
}

/**
 * Get sorted properties of an object, some special properties override the
 * alphanumeric sort order and are sorted at the begining
 */
function getProperties(obj) {
    var special = ['png', 'jpeg', 'jpg', 'har', 'html'];
    var props = [];

    for (var k in obj) {
        if(obj.hasOwnProperty(k)) {
            props.push(k);
        }
    }

    return props.sort(function(a, b){
        var indexA = special.indexOf(a);
        var indexB = special.indexOf(b);
        if(indexA == -1 && indexB == -1) {
            return a > b ? 1 : -1;
        } else if (indexA >= 0 && indexB >= 0) {
            return indexA - indexB;
        } else {
            return indexA == -1 ? 1 : -1;
        }
    });
}

function renderObject(obj, $cnt) {
    if(obj.log && obj.log.creator && obj.log.creator.name === 'Splash') { // Test if it's a har object
        $cnt.addClass('har')
            .append('<span class="type">HAR data</span>')
            .append(
                downloadButton(splash.pageName + '.har', "application/json;charset=utf-8", encodeURIComponent(JSON.stringify(obj)))
            ).append(loadHarViewer(obj));
        return;
    }
    if($.isArray(obj)) {
        $cnt.append('<span class="type">Array</span><span class="arrlen">[' + obj.length + ']</span>');
    } else {
        $cnt.append('<span class="type">Object</span>');
    }
    var props = getProperties(obj);
    for (var i = 0, len = props.length; i < len; i++) {
        var $subcnt = $('<span/>').addClass('obj-item');
        $('<div/>').addClass('obj-item indent')
            .append($('<span/>').addClass('key').text(props[i]))
            .append($('<span/>').addClass('colon').text(': '))
            .append($subcnt).appendTo($cnt);
        renderValue(obj[props[i]], $subcnt);
    }
}

function renderValue(obj, $cnt) {
    $cnt.addClass('value');
    if(obj === null) {
        $cnt.addClass('falsy').text('null');
    } else if (typeof obj === 'undefined') {
        $cnt.addClass('falsy').text('undefined');
    } else if (typeof obj === 'number' || typeof obj === 'boolean') {
        $cnt.addClass(typeof obj).text(obj);
    } else if (typeof obj === 'string') {
        renderString(obj, $cnt);
    } else if ($.isArray(obj) || typeof obj === 'object') {
        renderObject(obj, $cnt);
    } else {
        $cnt.text("Can't render object");
        console.error('Unknown object', obj);
    }
}

if(splash.params) {
    var pageName = splash.params.url, match;
    if((match = pageName.match(/\w+:\/\/([^\/]+)(\/|$)/)) !== null) {
        pageName = match[1];
    }
    splash.pageName = pageName.replace(/[^a-z0-9\.]+/g, '_');

    // Send request to splash
    $("#status").text("Rendering, please wait..");
    var xhr = new XMLHttpRequest();

    var onError = function onError(err){
        $("#errorStatus").text(xhr.status + " (" + xhr.statusText + ")");
        $("#errorData").text(JSON.stringify(err, null, 4));
        $("#errorMessage").show();
        $("#status").text("Error occured");
        $("#errorMessageText").text(err.info.message);
        $("#errorDescription").text(err.description);
        var errType = err.type;
        if (err.info.type){
            errType += ' -> ' + err.info.type;
        }
        $("#errorType").text(errType);
    };

    xhr.onreadystatechange = function(){
        if (this.readyState === 4){
            var blob = this.response;
            var reader = new FileReader();
            var isImage = /^image\//.test(blob.type);
            reader.addEventListener("loadend", function() {
                var data = reader.result;
                if(isImage) {
                    data = data.replace(/^data:[^;]+;[^,]+,/, '');
                } else if (/json/.test(blob.type)) {
                    data = JSON.parse(data);
                }
                if(xhr.status === 200) {
                    $('#result').show();
                    splash.result = data;
                    renderValue(data, $('#result').find('.obj-item'));
                    $("#status").text(data ? "Success" : "Empty result");
                } else {
                    onError(data);
                }
            });
            if(isImage) {
                data = reader.readAsDataURL(blob);
            } else {
                data = reader.readAsText(blob);
            }
        }
    };
    xhr.open('POST', splash.lua_enabled ? '/execute' : '/render.json');
    xhr.setRequestHeader('content-type', 'application/json');
    xhr.responseType = 'blob'; // Need blob in case an image is returned directly
    xhr.send(JSON.stringify(params));
}

})();
