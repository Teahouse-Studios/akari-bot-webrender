function section_screenshot_evaluate({ section, elements_to_disable }) {
  console.log(`Section: ${section}`); // skipcq
  console.log(`Elements to disable: ${elements_to_disable}`); // skipcq

  const levels = ["H1", "H2", "H3", "H4", "H5", "H6"];
  let sec = document.getElementById(section).parentNode;
  let sec_level = sec.tagName;
  if (sec.parentNode.className.includes("ext-discussiontools-init-section")) {
    // wo yi ding yao sha le ni men
    sec = sec.parentNode;
  }

  let nbox = document.createElement("div");
  nbox.className = "bot-sectionbox";
  nbox.style = "display: inline-block";
  nbox.appendChild(sec.cloneNode(true));

  let next_sibling = sec.nextSibling;
  while (next_sibling) {
    if (levels.includes(next_sibling.tagName)) {
      if (levels.indexOf(next_sibling.tagName) <= levels.indexOf(sec_level))
        break;
    }
    if (
      next_sibling.tagName === "DIV" &&
      next_sibling.className.includes("ext-discussiontools-init-section")
    ) {
      let child = next_sibling.firstChild;
      let bf = false;
      while (child) {
        if (
          levels.includes(child.tagName) &&
          levels.indexOf(child.tagName) <= levels.indexOf(sec_level)
        ) {
          bf = true;
          break;
        }
        child = child.nextSibling;
      }
      if (bf) break;
    }
    nbox.appendChild(next_sibling.cloneNode(true));
    next_sibling = next_sibling.nextSibling;
  }

  let lazyimg = nbox.querySelectorAll(".lazyload");
  for (let i = 0; i < lazyimg.length; i++) {
    lazyimg[i].className = "image";
    let dataSrc = lazyimg[i].getAttribute("data-src");
    if (
      typeof dataSrc === "string" &&
      (dataSrc.startsWith("http://") ||
        dataSrc.startsWith("https://") ||
        dataSrc.startsWith("/"))
    ) {
      lazyimg[i].src = dataSrc;
    } else {
      console.warn(`Blocked suspicious data-src value for image: ${dataSrc}`); // skipcq
    }
  }

  let new_parentNode = sec.parentNode.cloneNode();
  let pparentNode = sec.parentNode.parentNode;
  pparentNode.removeChild(sec.parentNode);
  pparentNode.appendChild(new_parentNode);
  new_parentNode.appendChild(nbox);

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
