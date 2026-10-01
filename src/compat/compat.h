/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef OBSERVER_COMPAT_H
#define OBSERVER_COMPAT_H
/* The build harness verifies the exact reference-tree manifest before choosing this. */
#if OBSERVER_EXIM_VERSION == 49905
#define OBSERVER_DEBUG DEBUG(D_load)
#elif OBSERVER_EXIM_VERSION == 410001
/* Native DEBUG(load) casts away const; is_debug itself accepts const. */
#define OBSERVER_DEBUG if (ANY_DEBUG && is_debug(CUS "load"))
#else
#error "Build only against inspected Exim 4.99.5 or 4.100.1"
#endif
#endif
