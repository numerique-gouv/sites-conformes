// Buttons and markers for the carousel (numerique_gouv/blocks/slider.html).
// Scrolling itself is handled in CSS (scroll-snap): this script is only an enhancement.
// It can be included several times on a page (once per carousel): each carousel
// is initialized only once.
(() => {
  const init = (slider) => {
    if (slider.dataset.ngSliderReady) return;
    slider.dataset.ngSliderReady = "true";

    const track = slider.querySelector(".ng-slider__track");
    const slides = Array.from(track.children);
    const controls = slider.querySelector(".ng-slider__controls");
    if (!controls || slides.length < 2) return;

    const prev = controls.querySelector("[data-ng-slider-prev]");
    const next = controls.querySelector("[data-ng-slider-next]");
    const markers = Array.from(controls.querySelectorAll("[data-ng-slider-goto]"));
    let current = 0;

    // Wraps around: "previous" on the first slide goes to the last one, and vice versa.
    // Smooth or instant scrolling comes from the CSS `scroll-behavior`,
    // which honors `prefers-reduced-motion`.
    const goTo = (index) => {
      const target = (index + slides.length) % slides.length;
      track.scrollTo({ left: slides[target].offsetLeft - slides[0].offsetLeft });
    };

    const update = (index) => {
      current = index;
      markers.forEach((marker, i) => {
        if (i === current) {
          marker.setAttribute("aria-current", "true");
        } else {
          marker.removeAttribute("aria-current");
        }
      });
    };

    prev.addEventListener("click", () => goTo(current - 1));
    next.addEventListener("click", () => goTo(current + 1));
    markers.forEach((marker) => {
      marker.addEventListener("click", () => goTo(Number(marker.dataset.ngSliderGoto)));
    });

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) update(slides.indexOf(entry.target));
        });
      },
      { root: track, threshold: 0.6 },
    );
    slides.forEach((slide) => observer.observe(slide));

    update(0);
    controls.hidden = false;
    slider.classList.add("ng-slider--enhanced");
  };

  const initAll = () => document.querySelectorAll("[data-ng-slider]").forEach(init);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
