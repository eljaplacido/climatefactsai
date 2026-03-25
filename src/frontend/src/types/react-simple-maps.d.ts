declare module "topojson-client" {
  export function feature(topology: any, object: any): any;
  export function mesh(topology: any, object: any, filter?: any): any;
}

declare module "d3-geo" {
  export function geoNaturalEarth1(): any;
  export function geoPath(projection?: any): any;
  export function geoMercator(): any;
}
