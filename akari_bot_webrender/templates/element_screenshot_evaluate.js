function element_screenshot_evaluate(elements_to_disable) {
    const images = document.querySelectorAll("img")
    images.forEach(image => {
        image.removeAttribute('loading');
    })
    const animated = document.querySelectorAll(".animated")
    for (var i = 0; i < animated.length; i++) {
        b = animated[i].querySelectorAll('img')
        for (ii = 0; ii < b.length; ii++) {
            b[ii].width = b[ii].getAttribute('width') / (b.length / 2)
            b[ii].height = b[ii].getAttribute('height') / (b.length / 2)
        }
        animated[i].className = 'nolongeranimatebaka'
    }
    for (var i = 0; i < elements_to_disable.length; i++) {
        const element_to_boom = document.querySelector(elements_to_disable[i])// :rina: :rina: :rina: :rina:
        if (element_to_boom != null) {
            element_to_boom.style = 'display: none !important'
        }
    }
    document.querySelectorAll('*').forEach(element => {
        element.parentNode.replaceChild(element.cloneNode(true), element);
    });
    window.scroll(0, 0)
}