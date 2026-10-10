async ({selector, content}) => {
  const target = document.querySelector(selector);
  if (!target) return false;

  const template = document.createElement("template");
  template.innerHTML = content;
  target.replaceChildren(template.content.cloneNode(true));
  target.dispatchEvent(new CustomEvent("akariwebrender:content-replaced", {
    bubbles: true,
    detail: {selector},
  }));

  const waitForEvent = (element) => new Promise((resolve) => {
    if (
      (element.tagName !== "IFRAME" && element.complete) ||
      (element.tagName === "IFRAME" && element.contentDocument?.readyState === "complete")
    ) {
      resolve();
      return;
    }
    let timer;
    const done = () => {
      clearTimeout(timer);
      element.removeEventListener("load", done);
      element.removeEventListener("error", done);
      resolve();
    };
    element.addEventListener("load", done, {once: true});
    element.addEventListener("error", done, {once: true});
    timer = setTimeout(done, 15000);
  });

  const resources = Array.from(target.querySelectorAll("img, iframe"));
  await Promise.all(resources.map(async (resource) => {
    await waitForEvent(resource);
    if (resource.tagName === "IMG" && resource.decode) {
      await resource.decode().catch(() => {});
    }
  }));
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  await new Promise(requestAnimationFrame);
  await new Promise(requestAnimationFrame);
  return true;
}
