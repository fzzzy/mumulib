
import { fill_body, clone_pat } from '../../src/patslot';

const examplePeople = [
  { name: 'John Doe', age: 30 },
  { name: 'Jane Smith', age: 25 },
  { name: 'Alice Johnson', age: 35 }
];

window.onload = async () => {
  const clonedNodes = await Promise.all(
    examplePeople.map(
      async person => await clone_pat('person', {
        name: person.name,
        age: person.age.toString()
      })
    )
  );
  await fill_body({ people: clonedNodes });
};
