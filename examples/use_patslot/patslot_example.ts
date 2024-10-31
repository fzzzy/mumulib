import { fill_body, clone_pat } from '../../src/patslot';

const examplePeople = [
  { name: 'John Doe', age: 30 },
  { name: 'Jane Smith', age: 25 },
  { name: 'Alice Johnson', age: 35 }
];

window.onload = () => {
  const clonedNodes = examplePeople.map(person => clone_pat('person', person));
  fill_body({ people: clonedNodes });
};
