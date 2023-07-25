import { useState } from "react";

interface props {
  list: string[];
}

function List({ list }: props) {
  let [selectedItem, setSelectedItem] = useState(-1);

  return (
    <div>
      <h1>Title</h1>
      <ul className="list-group">
        {list.map((item, index) => (
          <li
            className={
              selectedItem === index
                ? "list-group-item active"
                : "list-group-item"
            }
            key={item}
            onClick={() => setSelectedItem(index)}
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default List;
