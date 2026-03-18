import { KeyboardEvent, useState } from 'react';
import { useIntl } from 'react-intl';

interface Props {
  list: string[];
}

function List({ list }: Props) {
  const intl = useIntl();
  const [selectedItem, setSelectedItem] = useState(-1);

  const activateItem = (index: number) => {
    setSelectedItem(index);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLLIElement>, index: number) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      activateItem(index);
    }
  };

  return (
    <div>
      <h2>{intl.formatMessage({ id: 'common.title' })}</h2>
      <ul
        className="list-group"
        role="listbox"
        aria-label={intl.formatMessage({ id: 'common.items' })}
      >
        {list.map((item, index) => {
          const isSelected = selectedItem === index;
          const isFocusable = isSelected || (selectedItem === -1 && index === 0);

          return (
            <li
              className={isSelected ? 'list-group-item active' : 'list-group-item'}
              key={item}
              role="option"
              aria-selected={isSelected}
              tabIndex={isFocusable ? 0 : -1}
              onClick={() => activateItem(index)}
              onFocus={() => setSelectedItem(index)}
              onKeyDown={(event) => handleKeyDown(event, index)}
            >
              {item}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default List;
