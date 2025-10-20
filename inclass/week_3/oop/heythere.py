class person:
    __count  = 0
    __count_quee = 0
    __person_dict = dict()
    ls = []


    def __init__(self, name = "John Doe", age = 18, ):
        self.name = name
        self.__age = age
        person.__count += 1
        person.__count_quee += 1
        self.quee = person.__count_quee
        person.__person_dict[person.__count_quee] = [self.name , person.__count]
        print(f"say hi to {self.name}")
        print(person.__person_dict)
        person.ls.append(person.__count_quee)


    def __del__(self):
        person.__count -= 1
        person.__person_dict.pop(self.quee) 
        print(f"{self.name} is dead. {self.__count} people are left.")
        
        person.ls.remove(self.quee)
    
        for i in person.ls:
            idx = person.ls.index(i)
            person.__person_dict[i][1] = idx + 1

        print(person.__person_dict)


    def PrintAge(self):
        print(f"{self.name} is {self.__age} years old.")


    @property
    def Age(self):
        return self.__age
    
    @Age.setter
    def Age(self, age):

        if type(age) is int and age >= 0:
            self.__age = age

        else:
            print(f"dude {age} is not a valid age.")