function wait_for_element(splash, selector, maxwait)
    -- Wait until a selector matches an element in the page
    -- Return an error if waited more than maxwait seconds
    if maxwait == nil then
        maxwait = 10
    end
    return splash:wait_for_resume(string.format([[
        function main(splash) {
            var selector = '%s';
            var maxwait = %s;
            var end = Date.now() + maxwait*1000;

            function check() {
                if(document.querySelector(selector)) {
                    splash.resume('Element found');
                } else if(Date.now() >= end) {
                    splash.error('Timeout waiting for element ' + selector);
                } else {
                    setTimeout(check, 200);
                }
            }
            check();
        }
    ]], selector, maxwait))
end

function main(splash)
    splash:go("http://scrapinghub.com")
    wait_for_element(splash, "#foo")
    return {png=splash:png()}
end
