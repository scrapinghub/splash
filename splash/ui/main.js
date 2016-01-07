(function(){

var splash = window.splash || {};
var params = splash.params || {};

if(splash.lua_enabled) {
    $(document.body).removeClass('no-lua').addClass('has-lua');

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

    var autocomplete = function autocomplete(cm) {
        var cur = cm.getCursor(), line = cm.getRange({line: cur.line, ch:0}, cur);
        if (/splash:[a-z_]*$/.test(line)) {
            return CodeMirror.hint.fromList(cm, {words: splash.commands});
        }
    };

    var init_editor = function init_editor(){
        if(splash.lua_enabled && !splash.editor) {
            /* Create editor */
            var textarea = $('#lua-code-editor:visible');
            if (textarea.length) {
                textarea.val(params.lua_source || splash.example_script || "");
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

var harViewerLoaded = $.Deferred();

/* Initialize HAR viewer & send AJAX requests */
$("#content").bind("onViewerPreInit", function(event){
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

$("#content").bind("onViewerHARLoaded", function(event){
    $('#harviewer_loading').remove();
});

$("#content").bind("onViewerInit", function(event){
    var viewer = event.target.repObject;
    harViewerLoaded.resolve(viewer);
});

if(splash.params) {
    // Send request to splash
    $("#status").text("Rendering, please wait..");
    $.ajax(splash.lua_enabled ? '/execute' : '/render.json', {
        "contentType": "application/json",
        "dataType": "json",
        "type": "POST",
        "data": JSON.stringify(params)
    }).done(function(data){
        if (!data){
            $("#status").text("Empty result");
            return;
        }

        var har  = data.har;
        var png  = data.png;
        var jpeg = data.jpeg;
        var html = data.html;

        if (har){
            harViewerLoaded.then(function(viewer){
                viewer.appendPreview(har);
                var downloadLink = $('#har-download');
                var harData = "application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(har));
                downloadLink.attr("href", "data:" + harData);
                downloadLink.attr("download", "activity.har");
                downloadLink.show();
            });
        }
        if (png) {
            $(".pagePreview img").attr("src", "data:image/png;base64," + png);
        }
        if (jpeg) {
            $(".pagePreview img").attr("src", "data:image/jpeg;base64," + jpeg);
        }
        $("#renderedHTML").val(html);
        $(".pagePreview").show();
        $("#status").text("Success");
    }).fail(function(xhr, status, err){
        $("#errorStatus").text(xhr.status + " (" + err + ")");
        err = xhr.responseJSON;
        var resp = JSON.stringify(err, null, 4);
        $("#errorData").text(resp);
        $("#errorMessage").show();
        $("#status").text("Error occured");
        $("#errorMessageText").text(err.info.message);
        $("#errorDescription").text(err.description);

        var errType = err.type;
        if (err.info.type){
            errType += ' -> ' + err.info.type;
        }
        $("#errorType").text(errType);
    });
}

})();
