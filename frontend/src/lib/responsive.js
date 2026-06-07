/**
 * Responsive Design System
 * Breakpoints for mobile, tablet, and desktop
 */

/* Breakpoints */
export const breakpoints = {
  mobile: 320,      // Small phones
  mobileLarge: 480, // Large phones
  tablet: 768,      // Tablets
  desktop: 1024,    // Desktop
  desktopLarge: 1440, // Large desktop
  desktopXL: 1920   // Extra large desktop
};

/* Media Query Mixins (for reference, use in CSS) */
export const mediaQueries = {
  mobile: `@media (max-width: ${breakpoints.mobileLarge - 1}px)`,
  mobileUp: `@media (min-width: ${breakpoints.mobile}px)`,
  tablet: `@media (min-width: ${breakpoints.tablet}px)`,
  tabletOnly: `@media (min-width: ${breakpoints.tablet}px) and (max-width: ${breakpoints.desktop - 1}px)`,
  desktop: `@media (min-width: ${breakpoints.desktop}px)`,
  desktopLarge: `@media (min-width: ${breakpoints.desktopLarge}px)`,
  desktopXL: `@media (min-width: ${breakpoints.desktopXL}px)`
};

/* Device Type Detection Helper */
export function getDeviceType() {
  if (typeof window === 'undefined') return 'desktop';
  
  const width = window.innerWidth;
  
  if (width < breakpoints.tablet) return 'mobile';
  if (width < breakpoints.desktop) return 'tablet';
  return 'desktop';
}

export default {
  breakpoints,
  mediaQueries,
  getDeviceType
};
