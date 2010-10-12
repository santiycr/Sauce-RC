var LAST_TIME = 0;
var status_refresh_int = 3000;
var log_refresh_int = 1000;
var get_browsers_int = 600000;

var version_update_done = false;
var unsaved_prefs = false;
var alerted_ondemand = false;
var mode_focused = false;

var BROWSERS = null;

function update_select(id, values) {
    values.sort();
    $('#' + id + ' option').remove();
    for (var i in values) {
        var value = values[i];
        var html = '<option value="' + value + '">' + value + '</option>';
        $('#' + id).append($(html));
    }
}

function keys(obj) {
    var values = [];
    for (var v in obj) {
        values.push(v);
    }

    return values;
}

/* Why, oh why can't JavaScript compare objects? */
function array_equal(arr1, arr2) {
    if (arr1.length != arr2.length) {
        return false;
    }
    arr1.sort();
    arr2.sort();

    for (var i in arr1) {
        if (arr1[i] != arr2[i]) {
            return false;
        }
    }

    return true;
}

function browsers_equal(b1, b2) {
    if (!array_equal(keys(b1), keys(b2))) {
        return false;
    }

    for (var os in b1) {
        var n1 = b1[os];
        var n2 = b2[os];

        if (!array_equal(keys(n1), keys(n2))) {
            return false;
        }

        for (var name in n1) {
            var v1 = n1[name];
            var v2 = n2[name];

            if (!array_equal(v1, v2)) {
                return false;
            }
        }
    }

    return true;
}

function on_browser() {
    var os = $('#ondemand-os').val();
    var browser = $('#ondemand-browser').val();
    var versions = BROWSERS[os][browser];
    update_select('ondemand-browser-version', versions);
}

function on_os() {
    var os = $('#ondemand-os').val();
    update_select('ondemand-browser', keys(BROWSERS[os]));
    on_browser();
}

function log_refresh(){
    $.ajax({url: "log", 
            data: {last: LAST_TIME}, 
            cache: false,
            dataType: "json",
            success: function(data){log_arrived(data);},
            error: function(){setTimeout(log_refresh, log_refresh_int);}
           });
}

function class_wrap(line, text, wrap_class) {
    return line.replace(text, "<span class='" + wrap_class + "'>" + text + "</span>");
}
function log_arrived(data){
    if (data !== null) {
        LAST_TIME = data.last;
        if (data.log.length > 0) {
            log_div = $('#sel-output');
            var tmp = "";
            $.each(data.log,
                   function (i, line) {
                        if (line.indexOf("Command request") > 0) {
                            line = line.replace(/\b\[([^,]*), /g, "[<span class='value'>$1</span>, ");
                            line = line.replace(/, ([^,]*)(, )?\] on session/g, ", <span class='value'>$1</span>$2] on session");
                            line = line.replace(/Command request: (\w*)/, "Command request: <span class='command'>$1</span>");
                        } else if (line.indexOf("Got result") > 0) {
                            line = class_wrap(line, "OK", "ok");
                            line = class_wrap(line, "ERROR", "error");
                        } else if (line.indexOf("Starting new test") > 0) {
                            line = linkify(line);
                            line = class_wrap(line, "Starting new test", "important");
                        } else if (line.indexOf("Test Finished") > 0) {
                            line = linkify(line);
                            line = class_wrap(line, "Test Finished", "important");
                        } else if (line.indexOf("INFO") > 0 || line.indexOf("DEBUG") > 0) {
                            line = "<span class='secondary'>" + line + "</span>";
                        }
                        tmp += '<div>' + line + '</div>';
                   });
            log_div.append(tmp);
            if ($("#log-autoscroll").attr("checked")) {
                log_div.scrollTop(99999999);
            }
        }
    }
    setTimeout(log_refresh, log_refresh_int);
}

function status_refresh(){
    $.ajax({url: "status",
            cache: false,
            dataType: "json",
            success: function(response){status_arrived(response);},
            error: function(response){status_failed(response);}
           });
}

function status_arrived(response){
    /* This can happen */
    if (response === null) {
        status_failed(response);
        return;
    }

    update_controls($("#server-control"), response.running, response.ready);
    update_controls($("#tunnel-control"), response.tunnel_running, response.tunnel_ready);

    if (!mode_focused) {
        $("#mode").val(response.current_mode);
    }

    if (response.new_version) {
        new_version_div = $("#new_version");
        $(".version", new_version_div).text(response.new_version.version);
        $("#version_update_link", new_version_div).attr("href",
                                                        response.new_version.download_url);
        new_version_div.show();
    }

    if (!version_update_done) {
        aboutd = $("#about-dialog");
        $(".version", aboutd).text(response.current_version.version);
        $(".build", aboutd).text(response.current_version.build);
        $(".selenium-version", aboutd).text(response.current_version.selenium_version);
        document.title = document.title + " " + response.current_version.version;
        version_update_done = true;
    }

    disable_settings(response);

    if (($('#mode').val() == 'Sauce OnDemand') &&
        (!response.ondemand_reachable) &&
        (!alerted_ondemand)) {
        msg = message({title: "Sauce OnDemand is unreachable",
                       details: "Please check your internet connection",
                       type: "alert"});
        alerted_ondemand = true;
    } else if (response.ondemand_reachable && alerted_ondemand) {
        $("#alert-box").fadeOut("fast");
        alerted_ondemand = false;
    }

    if (response.htmlsuite_running && response.running) {
        message({title: "Please wait",
                 details: "A Selenese HTML suite is currently running",
                 time: 3}); // status will be called in 3 sec and message will look like fixed
        status_div.text("HTML Suite Running");
    }

    setTimeout(status_refresh, status_refresh_int);
}

function update_controls(control_div, running, ready){
    status_div = $(".status", control_div);
    if (running){
        $(".stop-control", control_div).show();
        $(".start-control", control_div).hide();
        status_div.removeClass("not-running");
        status_div.addClass("running");
        image = $(".running-img", status_div);
        if (ready) {
            image.stop(true).fadeTo('fast', 1);
        } else {
            image.effect("pulsate", {times: 2}, 1500);
        }
    } else {
        $(".start-control", control_div).show();
        $(".stop-control", control_div).hide();
        status_div.addClass("not-running");
        status_div.removeClass("running");
        image = $(".not-running-img", status_div);
    }

    $("img", status_div).not(image).hide();
    image.show();
}

function disable_settings(response){
    if (response.current_mode == "Selenium RC") {
        incorrect_prefs = $("#prefstabs-2");
        correct_prefs = $("#prefstabs-1");
    } else {
        incorrect_prefs = $("#prefstabs-1");
        correct_prefs = $("#prefstabs-2");
    }
    incorrect_prefs.addClass("ui-state-disabled")
                   .find(":input").focus(function(){
                       $('#incorrect-prefs-dialog').dialog('open');
                       return false;
                    }).click(function() {
                        $('#incorrect-prefs-dialog').dialog('open');
                        return false;
                    }).addClass("ignore"); //adding class for jquery validate to ignore
    correct_prefs.removeClass("ui-state-disabled")
        .find(":input")
        .unbind('focus')
        .unbind('click')
        .removeClass("ignore"); //removing class for jquery validate not to ignore
}

function status_failed(XMLHttpRequest, testStatus, errorThrown) {
    message({title: "Sauce RC seems to be down",
             details: "If you're not in the same machine where Sauce RC is running, please check the connection to that machine is still working",
             type: "alert",
             time: 5});
    image = $(".unknown-img", $(".status"));
    $("img", $(".status")).not(image).hide();
    image.show();
    setTimeout(status_refresh, status_refresh_int);
}

function prefs_refresh(){
    msg = message({title: "Refreshing preferences",
                   details: "Should take just a second"});
    $.ajax({url: "preferences",
            dataType: "json",
            cache: false,
            success: function(response){update_settings(response);}
            // TODO: warn user on error
           });
    msg.fadeOut("fast");
}

function update_browser_settings(settings) {
    $('#ondemand-os').val(settings['ondemand-os']);
    on_os();
    $('#ondemand-browser').val(settings['ondemand-browser'].toLowerCase()); //backwards compat
    on_browser();
    $('#ondemand-browser-version').val(settings['ondemand-browser-version']);
}

function update_settings(settings) {
    // Special settings
    if (settings["selenium-forcedBrowserMode"] !== false) {
        $("*[name=forcedBrowserMode]").attr("checked", true);
        $("#forced-browser [value=" +
                settings["selenium-forcedBrowserMode"] +
                "]")
            .attr("checked", true);
    } else {
        $("*[name=forcedBrowserMode]").attr("checked", false);
        $("#forced-browser input").attr("checked", false);
    }
    delete settings["selenium-forcedBrowserMode"];

    $(".cloner").prev().each(function(){
        cloned_name = $(this).attr("name");
        $("[name^=" + cloned_name  +"]").not($(this)).each(function(){
            $(this).parent().remove();
        });
        if (settings[cloned_name] instanceof Array){
            values = settings[cloned_name];
            settings[cloned_name] = values[0];
            for (i=1; i < values.length; i++){
                $(this).next().click();
                settings[cloned_name + "-" + i] = values[i];
            }
        }
    });
    update_browser_settings(settings);
    // Backwards compat
    settings["allmodes-port"] = (settings["allmodes-port"]) ? settings["allmodes-port"]: settings.port;
    // Checkboxes and inputs
    for (var key in settings) {
        var obj = $('*[name=' + key + ']');
        if (obj.is("input[type=text]")){
            obj.val(settings[key]);
        } else if (obj.is("input[type=checkbox]")){
            if (settings[key]){
                obj.attr("checked", true);
            } else {
                obj.attr("checked", false);
            }
        }
    }
    revise_settings();
    unsaved_prefs = false;
    $("#save-prefs").button("disable");
}

function prefs_saved(action, text){
    if (text == "OK"){
        message({title: "Preferences " + action + "d",
                 details: "Changes will be applied next time you restart Sauce RC",
                 time: 3
                });
        $('#save-dialog').dialog('open');
        unsaved_prefs = false;
        $("#save-prefs").button("disable");
    } else {
        substr = action.substring(0, action.length - 1);
        message({title: "Error " + substr + "ing preferences",
                 details: text,
                 type: "alert",
                 time: 5
                });
    }
}

function prefs_locally_changed(){
    if (unsaved_prefs) {
        return;
    }
    unsaved_prefs = true;
    $("#save-prefs").button("enable")
                    .effect("highlight", {}, 3000);
}

function revise_settings() {
    if($('#selenium-forcedBrowserMode').attr('checked')){
        $('#forced-browser').slideDown()
                            .find(':input')
                            .attr('disabled', false);
    } else {
        $('#forced-browser').slideUp()
                            .find(':input')
                            .attr('disabled', true)
                            .attr('checked', false);
    }
    if($('#selenium-proxyInjectionMode').attr('checked')){
        $('#proxyInjectionSubOpts').slideDown()
                                   .find(':input')
                                   .attr('disabled', false);
    } else {
        $('#proxyInjectionSubOpts').slideUp()
                                   .find(':input')
                                   .attr('disabled', true);
    }
}

function set_log_refresh(rate){
    log_refresh_int = parseInt(rate);
}

function message(data){
    if (data.type == "alert"){
        box = $("#alert-box");
    } else {
        box = $("#message-box");
    }
    $("strong", box).text(data.title);
    $(".message-detail", box).text(data.details);
    box.show();
    if (data.time){
        box.delay(data.time * 1000)
           .fadeOut("fast");
    }
    return box;
 }

function parse_prefs(){
    var fields = $('form#preferences').serializeArray();
    var results = {};
    $.each(fields, function(i, field){
        results[field.name] = field.value == "on" ?  true : field.value;
    });
    if (results['selenium-forcedBrowserMode']){
        results['selenium-forcedBrowserMode'] = results['selenium-browserForce'];
    } else {
        results['selenium-forcedBrowserMode'] = false;
    }
    delete results['selenium-browserForce'];
    if (results['selenium-proxyInjectionMode']) {
        if (results['selenium-userContentTransformation-regex'] && 
            results['selenium-userContentTransformation-replacement']){

            results['selenium-userContentTransformation'] = [
                results['selenium-userContentTransformation-regex'],
                results['selenium-userContentTransformation-replacement']];
        }
    } else {
        results['selenium-userContentTransformation'] = "";
        results['selenium-dontInjectRegex'] = "";
    }

    delete results['selenium-userContentTransformation-regex'];
    delete results['selenium-userContentTransformation-replacement'];

    $(".cloner").prev().each(function(){
        cloned_name = $(this).attr("name");
        value = results[cloned_name];
        results[cloned_name] = [];
        if (value) {
            results[cloned_name].push(value);
        }
        $("[name^=" + cloned_name +"]").not($(this)).each(function(){
            if(results[$(this).attr("name")]) {
                results[cloned_name].push(results[$(this).attr("name")]);
            }
            delete results[$(this).attr("name")];
        });
    });
    return results;
}

function restart_server(){
    $(this).dialog("close");
    $("#maintabs").tabs("select",0);
    $.ajax({url: "restart",
            cache: false,
            success: function(text){server_started(text, "Sauce RC");}
    });
}

function save_preferences(){
    if (unsaved_prefs) {
        prefs = parse_prefs();
        $.ajax({url: 'save',
                data: prefs,
                cache: false,
                success: function(text){prefs_saved("save", text);}
                //TODO: catch error and display it
               });
    }
    return false;
}

function restore_preferences(){
    $.ajax({url: 'restore',
            cache: false,
            success: function(text){prefs_saved("restore", text);}
            //TODO: catch error and display it
           });
}

function server_started(text, server){
    if (text != "OK"){
        message({title: server + " could not be started",
                 details: text,
                 type: "alert",
                 time: 5
                });
    }
}

function mode_switch_link() {
    $('#mode')[0].selectedIndex = ($('#mode')[0].selectedIndex + 1) % 2;
    $('#mode').change();
    $('#incorrect-prefs-dialog').dialog('close');
}

    
function switch_mode(){
    $.ajax({url: "switch", 
            data: {mode: $(this).val()},
            cache: false,
            success: function(data){switch_done(data)}
            //TODO: Better error on failure
           });

}

function switch_done(text){
    message({title: 'Mode has been changed',
             details: text,
             time: 5
            });
    if ($("#mode").val() == "Sauce OnDemand" &&
        $("#ondemand-username").val() === "" &&
        $("#ondemand-access-key").val() === ""){
        message({title: "Required preferences for OnDemand mode missing",
                 details: "Please provide your username and access-key",
                 type: "alert",
                 time: 7
                });
        $("#maintabs").tabs("select",2);
        $("#prefstabs").tabs("select",1);
        $("#ondemand-username").effect("highlight", {}, 5000);
        $("#ondemand-access-key").effect("highlight", {}, 5000);
    }
}

function browsers_arrived(browsers, textStatus, XMLHTTPRequest) {
    if ((BROWSERS === null) || ! browsers_equal(BROWSERS, browsers)) {
        var notify = (BROWSERS !== null);
        BROWSERS = browsers;
        if (BROWSERS) {
            update_select('ondemand-os', keys(BROWSERS));
            on_os();

            if (notify) {
                message({title: 'Browser information updated',
                         details: 'See Preferences/Sauce OnDemand',
                         time: 5});
            }
        }
    }
    setTimeout(get_browsers, get_browsers_int);
}

function get_browsers() {
    $.ajax({
        cache: false,
        dataType: 'json',
        success: browsers_arrived,
        error: function(){setTimeout(get_browsers, get_browsers_int/10);},
        url: '/browsers'
    });
}

function run_htmlsuite(){
        params = parse_htmlsuite_params();
        $.ajax({url: 'htmlsuite',
                data: params,
                cache: false
               });
        return false;
}

function parse_htmlsuite_params() {
    var fields = $('form#htmlsuite').serializeArray();
    return fields;
}

function clone_field(to_clone) {
    clon = to_clone.clone();
    clon_id = clon.attr("id");
    cloned_id = clon_id + "-" + $("[name^=" + clon_id +"]").length;
    clon.attr("id", cloned_id);
    clon.attr("name", cloned_id);
    clon.val("");
    new_line = $("<p />");
    $("<label />").appendTo(new_line);
    clon.appendTo(new_line);
    minus = $('<a href="#" title="Remove"><span class="ui-icon ui-icon-minus"></span></a>');
    minus.appendTo(new_line);
    minus.click(function(){$(this).parent().remove();
                           prefs_locally_changed();});
    to_clone.parent().after(new_line);
    return clon;
}

function startup(){
    $('#sel-output').text(""); /* Clear the log */
    get_browsers();
    prefs_refresh();
    status_refresh();
    log_refresh();

    // Buttons
    $('.start-control').button({icons: {primary: 'ui-icon-play'}}).hide();
    $('.stop-control').button({icons: {primary: 'ui-icon-stop'}}).hide();
    $('#clear-log').button({icons: {primary: 'ui-icon-trash'}});
    $('#get-full-log').button({icons: {primary: 'ui-icon-document'}});
    $('#refresh-prefs').button({icons: {primary: 'ui-icon-refresh'}});
    $('#restore-prefs').button({icons: {primary: 'ui-icon-refresh'}});
    $('#save-prefs').button({icons: {primary: 'ui-icon-disk'}})
                    .click(function(){$("form#preferences").submit();});
    $('#log-highlight').button();
    $('#log-autoscroll').button();
    $('#htmlsuite-submit').button({icons: {primary: 'ui-icon-play'}})
                          .click(function(){$("form#htmlsuite").submit();});

    // Tabs
    $('#maintabs').tabs();
    $('#prefstabs').tabs();

    $('#maintabs').bind('tabsselect', function(event, ui) {
        uitab = $(ui.tab);
        if (uitab.text() == "Preferences") {
            prefs_refresh();
        } else if (uitab.is("#maintabs>ul a") && unsaved_prefs) {
            $('#prefs-loss-dialog').dialog("open");
            return false;
        }
    });
    $('#maintabs').bind('tabsshow', function(event, ui) {
        uitab = $(ui.tab);
        if (uitab.text() == "Log") {
            if ($("#log-autoscroll").attr("checked")) {
                $('#sel-output').scrollTop(99999999);
            }
        }
    });

    // Tooltips
//  $('*[title]').tooltip();
//  Waiting for the jquery ui team :)

    // Dialogs
    $('#save-dialog').dialog({autoOpen: false,
                              title: "Apply preferences",
                              width: 600,
                              position: ['center', 100],
                              buttons: {"Restart": function(){
                                                  restart_server();
                                                  $(this).dialog("close");
                                              },
                                        "Cancel": function(){$(this).dialog("close");}}
                             });

    $('#restore-dialog').dialog({autoOpen: false,
                                 title: "Confirm restore",
                                 width: 600,
                                 position: ['center', 100],
                                 buttons: {"Restore": function(){
                                                          restore_preferences();
                                                          $(this).dialog("close");
                                                       },
                                           "Cancel": function(){$(this).dialog("close");}}
                        });

    $('#prefs-loss-dialog').dialog({autoOpen: false,
                              title: "Unsaved preferences will be lost",
                              width: 600,
                              position: ['center', 100],
                              buttons: {"Proceed anyway": function(){
                                                                    unsaved_prefs = false;
                                                                    $("#maintabs").tabs("select",0);
                                                                    $(this).dialog("close");},
                                        "Cancel": function(){$(this).dialog("close");}}
                             });


    $('#prefs-refresh-dialog').dialog({autoOpen: false,
                              title: "Unsaved preferences will be lost",
                              width: 600,
                              position: ['center', 100],
                              buttons: {"Proceed anyway": function(){prefs_refresh();
                                                                    $(this).dialog("close");},
                                        "Cancel": function(){$(this).dialog("close");}}
                             });


    $('#about-dialog').dialog({autoOpen: false,
                               title: "About Sauce RC",
                               width: 600,
                               resizable: false,
                               position: ['center', 100]
                        });

    $('#incorrect-prefs-dialog').dialog({autoOpen: false,
                                         title: "Incorrect preferences",
                                         width: 600,
                                         position: ['center', 100]
                        });

    $('#mode-switch-link').click(mode_switch_link);

    // Options
    $('#mode').change(switch_mode);
    $('form#preferences :input').live("change", prefs_locally_changed);

    // Special options

    // Hack for IE as it doesn't trigger the change event until you blur
    if ($.browser.msie) {
        $('#selenium-proxyInjectionMode').click(function() {
            this.blur();
            this.focus();
        });
        $('#selenium-forcedBrowserMode').click(function() {
            this.blur();
            this.focus();
        });
    }

    $('#selenium-proxyInjectionMode').change(revise_settings);
    $('#selenium-forcedBrowserMode').change(revise_settings);
    $('#ondemand-os').change(on_os);
    $('#ondemand-browser').change(on_browser);

    // Buttons
    $('#restore-prefs').click(function(){$('#restore-dialog').dialog('open');
                                         return false;
                                         });
    $('#refresh-prefs').click(function(){
        if (unsaved_prefs) {
            $('#prefs-refresh-dialog').dialog('open');
        } else {
            prefs_refresh();
        }
        return false;
    });
    $("#start-server").click(function(e){
       $.ajax({url: "start",
               cache: false,
               success: function(text){server_started(text, "Sauce RC");}
              });
       return false;
    });

    $("#stop-server").click(function(e){
        $.ajax({url: "stop",
                cache: false
               });
       return false;
    });

    $("#start-tunnel").click(function(e){
       $.ajax({url: "tunnel_start",
               cache: false,
               success: function(text){server_started(text, "Sauce Tunnel");}
              });
       return false;
    });

    $("#stop-tunnel").click(function(e){
        $.ajax({url: "tunnel_stop",
                cache: false,
                success: log_refresh
               });
       return false;
    });

    $("#log-refresh-rate").change(function(){
        set_log_refresh($(this).val());
    });

    $("#log-highlight").change(function(){
        log_div = $('#sel-output');
        if ($(this).attr("checked")) {
            log_div.addClass('highlight');
        } else {
            log_div.removeClass('highlight');
        }
    });

    $(".cloner").click(function(){
        clon = clone_field($(this).prev());
        clon.focus();
    });

    // Footer
    $('#about').click(function(){$('#about-dialog').dialog('open');
                                 return false;
                                });
    $('#clear-log').click(function() { $('#sel-output').empty(); return false;});
    $('#mode').focus(function() { mode_focused = true;});
    $('#mode').blur(function() { mode_focused = false;});
    // Fixed urls for auto open
    hash = window.location.hash;
    if (hash == "#oabout"){
        $("#about-dialog").dialog("open");
    } else if (hash == "#opreferences") {
        $("#maintabs").tabs("select",2);
    }

    $('form#preferences').validate({ignoreTitle: true,
                                    submitHandler: save_preferences,
                                    ignore: ".ignore",
                                    rules: {"allmodes-port": {required: true,
                                                              number: true},
                                            "selenium-timeout": {number: true},
                                            "selenium-profilesLocation": {remote: "/check_dir"},
                                            "selenium-firefoxProfileTemplate": {remote: "/check_dir"},
                                            "selenium-userExtensions": {accept: "user-extensions.js",
                                                                        remote: "/check_file"},
                                            "ondemand-username": {required: true},
                                            "ondemand-max-duration": {number: true},
                                            "ondemand-access-key": {required: true},
                                            "ondemand-user-extensions-url": {url: true,
                                                                             accept: "js"},
                                            "ondemand-firefox-profile-url": {url: true,
                                                                             accept: "zip"},
                                            "tunnel-port": {number: true}
                                           },
                                    messages: {"selenium-userExtensions": {accept: "User extensions file can only be named user-extensions.js",
                                                                           remote: "user-extensions.js file not found"},
                                               "selenium-profilesLocation": {remote: "Profile location not found"},
                                               "selenium-firefoxProfileTemplate": {remote: "Profile Template directory not found"},
                                               "ondemand-firefox-profile-url": {accept: "Firefox Profiles used in Ondemand can only be sent as zip files"},
                                               "ondemand-user-extensions-url": {accept: "User extensions used in Ondemand can only be js files"}
                                   }});

    $("form#htmlsuite").validate({ignoreTitle: true,
                                  submitHandler: run_htmlsuite,
                                  rules: {suiteFile: {required: true,
                                                      accept: "html",
                                                      remote: "/check_file"},
                                          resultFile: {required: true,
                                                       accept: "html"},
                                          startURL: {required: true,
                                                     url: true},
                                          htmlsuiteBrowser: {required: true}
                                          },
                                  messages: {suiteFile: {accept: "Only Selense HTML suites are accepted",
                                                         remote: "Suite file not found"},
                                             resultFile: {accept: "Only HTML output files are accepted"},
                                             startURL: {url: "You must provide a valid url for your tests to run"},
                                             htmlsuiteBrowser: {required: "You must choose a browser for the tests to run"}
                                            }

                                 });

    $("#maintabs").height($("#maintabs").height() + ($(window).height() - $("body").height()) - 20);
}

$(startup);
