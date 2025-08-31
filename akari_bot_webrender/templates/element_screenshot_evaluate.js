function element_screenshot_evaluate(elements_to_disable) {
  let images = document.querySelectorAll("img");
  images.forEach((image) => {
    image.removeAttribute("loading");
  });

  let animated = document.querySelectorAll(".animated");
  for (let i = 0; i < animated.length; i++) {
    let img = animated[i].querySelectorAll("img");
    for (let ii = 0; ii < img.length; ii++) {
      img[ii].width = img[ii].getAttribute("width") / (img.length / 2);
      img[ii].height = img[ii].getAttribute("height") / (img.length / 2);
    }
    animated[i].className = "nolongeranimatebaka";
  }

  for (let i = 0; i < elements_to_disable.length; i++) {
    let element_to_boom = document.querySelector(elements_to_disable[i]); // :rina: :rina: :rina: :rina:
    if (element_to_boom != null) {
      element_to_boom.style = "display: none !important";
    }
  }

  document.querySelectorAll("*").forEach((element) => {
    element.parentNode.replaceChild(element.cloneNode(true), element);
  });

  window.scroll(0, 0);
}
