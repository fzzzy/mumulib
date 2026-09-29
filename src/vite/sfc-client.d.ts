// What importing a .sfc.html gives TypeScript: the component's class. A
// project using the plugin references it, as it does vite/client:
//
//     /// <reference types="mumulib/sfc-client" />
declare module '*.sfc.html' {
  const component: CustomElementConstructor
  export default component
}
