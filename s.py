import requests
import json

# GraphQL introspection query для отримання всіх полів типу Media (аніме та манга)
introspection_query = '''
query {
  __type(name: "Media") {
    name
    description
    fields {
      name
      description
      type {
        name
        kind
        ofType {
          name
          kind
        }
      }
    }
  }
}
'''

# Запит для прикладу отримання даних саме про АНІМЕ з медіа-типу
anime_example_query = '''
query {
  # Це запит виключно для АНІМЕ контенту
  Page {
    media(type: ANIME) {
      id
      title {
        romaji
        english
        native
      }
    }
  }
}
'''

# Додайте цей код для отримання схеми типу MediaStreamingEpisode
streaming_episode_query = '''
query {
  __type(name: "MediaStreamingEpisode") {
    name
    description
    fields {
      name
      description
      type {
        name
        kind
        ofType {
          name
          kind
        }
      }
    }
  }
}
'''

# Також отримайте схему типу MediaCoverImage
cover_image_query = '''
query {
  __type(name: "MediaCoverImage") {
    name
    description
    fields {
      name
      description
      type {
        name
        kind
        ofType {
          name
          kind
        }
      }
    }
  }
}
'''

# Запит для отримання детальних даних про Attack on Titan
attack_on_titan_query = '''
query {
  Media(id: 16498, type: ANIME) {
    id
    idMal
    title {
      romaji
      english
      native
      userPreferred
    }
    description
    coverImage {
      extraLarge
      large
      medium
      color
    }
    bannerImage
    format
    status
    episodes
    duration
    genres
    tags {
      id
      name
      description
      category
    }
    averageScore
    popularity
    seasonYear
    season
    studios {
      nodes {
        id
        name
      }
    }
    startDate {
      year
      month
      day
    }
    endDate {
      year
      month
      day
    }
    streamingEpisodes {
      title
      thumbnail
      url
      site
    }
    trailer {
      id
      site
      thumbnail
    }
    airingSchedule {
      nodes {
        episode
        airingAt
        timeUntilAiring
      }
    }
    characters(sort: ROLE) {
      edges {
        node {
          id
          name {
            full
          }
          image {
            large
          }
          gender
          description
        }
        role
      }
    }
    recommendations {
      nodes {
        mediaRecommendation {
          id
          title {
            romaji
          }
          coverImage {
            medium
          }
        }
      }
    }
  }
}
'''

url = 'https://graphql.anilist.co'
response = requests.post(url, json={'query': introspection_query})
data = response.json()

# Виконайте запити
streaming_response = requests.post(url, json={'query': streaming_episode_query})
cover_response = requests.post(url, json={'query': cover_image_query})

# Збережіть схеми у файли
streaming_data = streaming_response.json()
cover_data = cover_response.json()

print("АНІМЕ ДАНІ У ANILIST API")
print("========================\n")

# Виведення всіх полів у зручному форматі
if '__type' in data.get('data', {}):
    media_type = data['data']['__type']
    print(f"Тип: {media_type['name']} (використовується для АНІМЕ)")
    print(f"Опис: {media_type['description']}")
    print("\nДоступні поля для АНІМЕ даних:")
    
    fields = sorted(media_type['fields'], key=lambda x: x['name'])
    for field in fields:
        field_type = field['type']
        if field_type.get('name'):
            type_name = field_type['name']
        elif field_type.get('ofType') and field_type['ofType'].get('name'):
            type_name = field_type['ofType']['name']
        else:
            type_name = field_type['kind']
            
        print(f"- {field['name']}: {type_name}")
        if field['description']:
            print(f"  Опис: {field['description']}")
        
    # Збереження повних даних у JSON файл для подальшого аналізу
    with open('anilist_media_schema.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        print("\nПовна схема збережена у файл 'anilist_media_schema.json'")
else:
    print("Помилка отримання даних:", data)

with open('anilist_streaming_schema.json', 'w', encoding='utf-8') as f:
    json.dump(streaming_data, f, ensure_ascii=False, indent=2)

with open('anilist_cover_schema.json', 'w', encoding='utf-8') as f:
    json.dump(cover_data, f, ensure_ascii=False, indent=2)

# Виконання запиту
aot_response = requests.post(url, json={'query': attack_on_titan_query})
aot_data = aot_response.json()

# Збереження в JSON файл
with open('attack_on_titan_data.json', 'w', encoding='utf-8') as f:
    json.dump(aot_data, f, ensure_ascii=False, indent=2)

# Виведення на екран
print("\nДані для 'Attack on Titan':")
print("=========================")
print("ID:", aot_data.get('data', {}).get('Media', {}).get('id'))
print("Назва:", aot_data.get('data', {}).get('Media', {}).get('title', {}).get('english'))

# Перевіримо наявність streaming episodes з thumbnails
streaming_episodes = aot_data.get('data', {}).get('Media', {}).get('streamingEpisodes', [])
print(f"\nКількість streaming episodes: {len(streaming_episodes)}")
if streaming_episodes:
    print("Приклад thumbnail URL:", streaming_episodes[0].get('thumbnail'))
    print("Приклад сайту:", streaming_episodes[0].get('site'))
else:
    print("Для цього аніме немає streaming episodes з thumbnails.")

# Перевірка наявності трейлера з thumbnail
trailer = aot_data.get('data', {}).get('Media', {}).get('trailer', {})
if trailer and trailer.get('thumbnail'):
    print("\nТрейлер thumbnail:", trailer.get('thumbnail'))
else:
    print("\nДля цього аніме немає трейлера з thumbnail.")