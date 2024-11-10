

import { patslot } from '../../src';


const dataset = {
  towns: [
    {
      name: "Los Angeles",
      people: [
        {"name": "Joe Smith", age: 67},
        {"name": "Example Person", age: 2}
      ]
    },
    {
      name: "London",
      people: [
        {"name": "Jane Smith", age: 23},
        {"name": "John Doe", age: 34}
      ]
    }
  ]
};


function render_people(people) {
  return people.map((person) => patslot.clone_pat("person", person));
}


function* render_towns(towns) {
  for (const town of towns) {
    yield patslot.clone_pat("town", {
      town_name: town.name,
      people: render_people(town.people)
    });
  }
}


window.onload = async () => {
  patslot.fill_body({
    towns: await render_towns(dataset.towns),
    footer: "This is the footer."
  });
}


