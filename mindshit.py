# Imports
from typing import Callable, Iterable, TypeVar, Union, List, Tuple
import json, sys

Self = TypeVar('Self')
Node = TypeVar('Node')

# Constants
DIGITS = '0123456789'
LETTERS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZŠŒŽšœžŸÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþ'
WHITESPACE = ' \t\n'

# Position
class Position:
    def __init__(self, index: int, line: int, column: int, file_name: str, file_text: str) -> None:
        self.index = index
        self.line = line
        self.column = column
        self.file_name = file_name
        self.file_text = file_text
        
    def next(self, char: str = None) -> Self:
        self.index += 1
        self.column += 1
        
        if char == '\n':
            self.line += 1
            self.column = 0
        
        return self
    
    def copy(self) -> Self:
        return Position(self.index, self.line, self.column, self.file_name, self.file_text)

# Error
class Error:
    def __init__(self, name: str, info: str, start: Position, end: Position = None) -> None:
        self.name = name
        self.info = info
        self.start = start
        self.end = end
        if not end:
            self.end = start.copy().next()
    
    def __str__(self) -> str:
        result = f'{self.name}: {self.info}\n'
        result += f'File "{self.start.file_name}", line {self.start.line + 1}\n'
        result += self.point()
        return result

    def point(self) -> str:
        result = ''

        # Calculate indices
        start_index = max(self.start.file_text.rfind('\n', 0, self.start.index), 0)
        end_index = self.start.file_text.find('\n', start_index + 1)
        
        if end_index < 0:
            end_index = len(self.start.file_text)
        
        # Generate each line
        line_count = self.end.line - self.start.line + 1
        for i in range(line_count):
            # Calculate line columns
            line = self.start.file_text[start_index:end_index]
            column_start = self.start.column if i == 0 else 0
            column_end = self.end.column if i == line_count - 1 else len(line) - 1

            # Append to result
            result += line + '\n'
            result += ' ' * column_start + '^' * (column_end - column_start)

            # Re-calculate indices
            start_index = end_index
            end_index = self.start.file_text.find('\n', start_index + 1)
            
            if end_index < 0:
                end_index = len(self.start.file_text)

        return result.replace('\t', '')
    

class IllegalCharError(Error):
    def __init__(self, info: str, start: Position, end: Position = None) -> None:
        super().__init__('Illegal Character', info, start, end)
    

class InvalidSyntaxError(Error):
    def __init__(self, info: str, start: Position, end: Position = None) -> None:
        super().__init__('Invalid Syntax', info, start, end)

# Tokens
class Tk:
    KW = 'kw'
    OP = 'op'
    ID = 'id'

    INT = 'int'
    CHAR = 'char'
    STR = 'string'

    EOF = 'eof'

    KEYWORDS = [
        # Loop blocks
        'while',
        'end',
        
        # Conditional blocks
        'if',
        'elif',
        'else',
        
        'do',
        
        # Boolean literals
        'true',
        'false',
        
        # Logical operators
        'and',
        'or',
        'not',
        
        # IO
        'print',
        'input',
    ]
    
    OPERATORS = [
        # Data relocation
        '<->', '->',
        
        # Arithmetic assignment
        '+=', '-=', '*=', '/=',
        
        # Comparison
        '==', '!=', '<=', '>=',
        '<', '>',
        
        # Misc
        '&', '=', ':',
        
        # Brackets
        '(', ')', '[', ']',
        
        # Arithmetic
        '+', '-', '*', '/', '%',
    ]

class Token:
    def __init__(self, type_: str, value: str = None, start: Position = None, end: Position = None) -> None:
        self.type = type_
        self.value = value
        
        self.full = (self.type)
        if self.value:
            self.full = (self.type, self.value)
        
        if start:
            self.start = start.copy()
            self.end = start.copy().next()
        
        if end:
            self.end = end.copy()
    
    def __repr__(self) -> str:
        if self.value != None:
            return f'[{self.type}: {self.value}]'
        return f'[{self.type}]'
    
    def reprJSON(self) -> dict:
        if self.value != None:
            return dict(type=self.type, value=self.value)
        return dict(type=self.type)

class Lexer:
    def __init__(self, file_name: str, text: str) -> None:
        self.file_name = file_name
        self.text = text
        self.pos = Position(-1, 0, -1, file_name, text)
        self.char = None
        self.next()
    
    def next(self, count: int = 1) -> Self:
        for _ in range(count):
            self.pos.next(self.char)
        
        self.char = self.text[self.pos.index] if self.pos.index < len(self.text) else None
        
        return self
    
    def lex(self) -> Tuple[List[Token], Error]:
        tokens = []
        
        while self.char != None:
            if self.char in WHITESPACE:
                self.next()
                
            elif self.char in DIGITS:
                tokens.append(self.make_number())
            
            elif self.char in LETTERS:
                tokens.append(self.make_text())
            
            elif self.char in ["'", '"']:
                token, error = self.make_char()
                if error: return [], error
                tokens.append(token)
            
            elif self.chars(2) == '//':
                self.skip_oneline_comment()
                
            elif self.chars(2) == '/*':
                self.skip_multiline_comment()
            
            else:
                for op in Tk.OPERATORS:
                    if self.chars(len(op)) == op:
                        tokens.append(Token(Tk.OP, op, self.pos))
                        self.next(len(op))
                        break
                else:
                    return [], IllegalCharError(f"'{self.char}'", self.pos)
        
        tokens.append(Token(Tk.EOF, start=self.pos))
        
        return tokens, None
    
    
    def chars(self, length: int) -> str:
        chars = ''
        pointer = self.pos.copy()
        
        for _ in range(length):
            if pointer.index >= len(self.text):
                return None
            
            chars += self.text[pointer.index]
            pointer.next(self.text[pointer.index])
        
        return chars
    
    def make_number(self) -> Tuple[Token, Error]:
        num_str = ''
        start_pos = self.pos.copy()
        
        while self.char != None and self.char in DIGITS:
            num_str += self.char
            self.next()
        
        return Token(Tk.INT, int(num_str), start_pos, self.pos)
    
    def make_text(self) -> Tuple[Token, Error]:
        text_str = ''
        start_pos = self.pos.copy()
        
        while self.char != None and self.char in LETTERS + DIGITS + '_':
            text_str += self.char
            self.next()
        
        token_type = Tk.KW if text_str in Tk.KEYWORDS else Tk.ID
        
        return Token(token_type, text_str, start_pos, self.pos)

    def make_char(self) -> Tuple[Token, Error]:
        text_str = ''
        start_pos = self.pos.copy()
        quote_type = self.char
        
        self.next()
        
        while self.char != None and self.char != quote_type:
            text_str += self.char
            self.next()
        
        self.next()
        
        return Token(Tk.CHAR if len(text_str) == 1 else Tk.STR, text_str, start_pos, self.pos), None
    
    def skip_oneline_comment(self) -> None:
        while self.char != None and self.char != '\n':
            self.next()
    
    def skip_multiline_comment(self) -> None:
        while self.char != None and self.chars(2) != '*/':
            self.next()
        self.next(2)

class LiteralNode:
    def __init__(self, value: int) -> None:
        self.value = value
    
    def reprJSON(self) -> str:
        return dict(value=self.value)

class AddressNode:
    def __init__(self, address: int) -> None:
        self.address = address
    
    def reprJSON(self) -> str:
        return dict(address=self.address)
    
class ArrayNode:
    def __init__(self, array: List[AddressNode]):
        self.array = array
        self.index = 0
        
    def reprJSON(self) -> str:
        return dict(array=self.array)

class IdentifierNode:
    def __init__(self, title: str) -> None:
        self.title = title
    
    def reprJSON(self) -> str:
        return dict(title=self.title)

class BinaryOpNode:
    def __init__(self, left: Node, token, right) -> None:
        self.left = left
        self.token = token
        self.right = right
    
    def reprJSON(self) -> str:
        return dict(token=self.token, left=self.left, right=self.right)

class UnaryOpNode:
    def __init__(self, token, right) -> None:
        self.token = token
        self.right = right
    
    def reprJSON(self) -> str:
        return dict(token=self.token, right=self.right)

class ConditionalNode:
    def __init__(self, token, condition, body, elsebody = []) -> None:
        self.token = token
        self.condition = condition
        self.body = body
        self.elsebody = elsebody
    
    def reprJSON(self) -> str:
        return dict(token=self.token, condition=self.condition, body=self.body, elsebody=self.elsebody)

class DoNode:
    def __init__(self, name, body) -> None:
        self.name = name
        self.body = body
    
    def reprJSON(self) -> str:
        return dict(name=self.name, body=self.body)

class Parser:
    def __init__(self, file_name, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.index = -1
        
        self.location = [DoNode(file_name, [])]
        
        self.next()
    
    def next(self, index: int = 1) -> Token:
        self.index += index
        self.token = self.tokens[self.index] if self.index < len(self.tokens) else None
        return self.token
           
    # TODO: create parsing errors
    def parse(self) -> Tuple[DoNode, Error]:
        # TODO: implement "include" for including tokens of another file
        while self.token.full != Tk.EOF:
            expr, error = self.expr()
            if error:
                return None, error
            self.location[-1].body.append(expr)
        
        return self.location[-1], None

    def unary_op(self, ops: List[Tuple[str]], function: Callable) -> UnaryOpNode:
        while self.token.full in ops:
            op_token = self.token
            self.next()
            right, error = function()
            return UnaryOpNode(op_token, right), error
        return function()
    
    def binary_op(self, ops: List[Tuple[str]], function: Callable) -> Union[BinaryOpNode, UnaryOpNode]:
        left, error = function()
        while self.token.full in ops:
            op_token = self.token
            self.next()
            right, error = function()
            left = BinaryOpNode(left, op_token, right)
        return left, error

    def conditional_op(self, ops: List[Tuple[str]], function: Callable) -> Union[ConditionalNode, BinaryOpNode, UnaryOpNode]:
        if self.token.full in ops:
            op_token = self.token
            self.next()
            condition, error = function()
            blocknode = ConditionalNode(op_token, condition, [])
            
            while not self.token.full in [(Tk.KW, 'end'), (Tk.KW, 'else'), (Tk.KW, 'elif')]:
                instruction, error = self.expr()
                blocknode.body.append(instruction)
                
            childblocknode = blocknode
                
            while self.token.full == (Tk.KW, 'elif'):
                op_token = self.token
                self.next()
                condition, error = function()
                newblocknode = ConditionalNode(op_token, condition, [])
                
                while not self.token.full in [(Tk.KW, 'end'), (Tk.KW, 'else'), (Tk.KW, 'elif')]:
                    instruction, error = self.expr()
                    newblocknode.body.append(instruction)
                
                childblocknode.elsebody = [newblocknode]
                childblocknode = newblocknode
                
            if self.token.full == (Tk.KW, 'else'):
                self.next()
                while self.token.full != (Tk.KW, 'end'):
                    instruction, error = self.expr()
                    childblocknode.elsebody = []
                    childblocknode.elsebody.append(instruction)
                
            if self.token.full == (Tk.KW, 'end'):
                self.next()
            
            return blocknode, error
        return function()
    
    # TODO: implement switch/match block
    
    # TODO: implement inline functions and function calls
    
    # TODO: implement data structures
    
    def expr(self) -> Union[ConditionalNode, BinaryOpNode, UnaryOpNode]:
        return  self.conditional_op([(Tk.KW, 'while'), (Tk.KW, 'if')],
        lambda: self.binary_op([(Tk.OP, '='), (Tk.OP, '+='), (Tk.OP, '-='), (Tk.OP, '*='), (Tk.OP, '/='), (Tk.OP, '->'), (Tk.OP, '<->')], 
        lambda: self.binary_op([(Tk.KW, 'or')],
        lambda: self.binary_op([(Tk.KW, 'and')],
        lambda: self.unary_op([(Tk.KW, 'not')],
        lambda: self.binary_op([(Tk.OP, '=='), (Tk.OP, '!='), (Tk.OP, '>'), (Tk.OP, '<'), (Tk.OP, '>='), (Tk.OP, '<=')],
        lambda: self.binary_op([(Tk.OP, '+'), (Tk.OP, '-')],
        lambda: self.binary_op([(Tk.OP, '*'), (Tk.OP, '/'), (Tk.OP, '%')],
        lambda: self.binary_op([(Tk.OP, ':')],
        lambda: self.unary_op([(Tk.KW, 'input')],
        lambda: self.unary_op([(Tk.KW, 'print')], 
                self.factor
        )))))))))))
            
    def factor(self) -> Node:
        token = self.token
        self.next()
        
        if token.type == Tk.INT:
            return LiteralNode(token.value), None
        
        if token.type == Tk.CHAR:
            return LiteralNode(ord(token.value)), None
        
        if token.type == Tk.STR:
            return ArrayNode([LiteralNode(ord(char)) for char in token.value]), None

        if token.full == (Tk.KW, 'true'):
            return LiteralNode(1), None
        
        if token.full == (Tk.KW, 'false'):
            return LiteralNode(0), None
        
        if token.full == (Tk.OP, '&'):
            address_token = self.token
            self.next()
            return AddressNode(address_token.value), None
        
        if token.full == (Tk.KW, 'do'):
            donode = DoNode('do', [])
            while self.token.full not in [(Tk.EOF), (Tk.KW, 'end')]:
                expr, error = self.expr()
                if error:
                    return None, error
                donode.body.append(expr)
            self.next()
            return donode, None
        
        if token.full == (Tk.OP, '['):
            array = ArrayNode([])
            while self.token.full not in [(Tk.EOF), (Tk.OP, ']')]:
                element, error = self.expr()
                array.array.append(element)
            self.next()
            return array, None

        if token.full == (Tk.OP, '('):
            expr = self.expr()
            if self.token.full == (Tk.OP, ')'):
                self.next()
                return expr

        if token.type == Tk.ID:
            return IdentifierNode(token.value), None
        
        return None, Error('Exception Raised', 'invalid factor', token.start, token.end)

# Infinity-simulating list
class InfiniteList:
    def __init__(self, object):
        self.object = object
        self.list = []
        
    def __getitem__(self, index):
        try:
            return self.list[index]
        except IndexError:
            self.list += [self.object for _ in range(index+1 - len(self.list))]
            return self.list[index]
    
    def __setitem__(self, index, value):
        try:
            self.list[index] = value
        except IndexError:
            self.list += [self.object for _ in range(index+1 - len(self.list))]
            self.list[index] = value
            
    def __iter__(self) -> Iterable:
        return iter(self.list)
    
    def __repr__(self) -> str:
        return str(self.list)

# Infinity-like list of boolean values indicating whether each slot is used
class MemoryUsageList(InfiniteList):
    def __init__(self) -> None:
        super().__init__(False)
    
    def use(self, *indices) -> None:
        for index in indices:
            self[index] = True
    
    def rmv(self, *indices) -> None:
        for index in indices:
            self[index] = False
    
    def get_cell(self) -> int:
        for index, value in enumerate(self.list):
            if not value:
                return index
        self[len(self.list)] = False
        return len(self.list) - 1
    
    def get_array(self, size: int) -> int:
        total_size = 0
        start_index = None
        for index, used in enumerate(self.list):
            if not used:
                total_size += 1
            else:
                total_size = 0
                
            if total_size == 1:
                start_index = index
                
            if total_size == size:
                return start_index
        self[len(self.list)-1+size] = False
        return len(self.list)-size
    
    def allocate(self, count: int = 1) -> int:
        if count == 1:
            cell_found = self.get_cell()
            self.use(cell_found)
            return cell_found
        cells = []
        for _ in range(count):
            cell_found = self.get_cell()
            self.use(cell_found)
            cells.append(cell_found)
        return tuple(cells)
    
    def allocate_array(self, size: int) -> int:
        array_found = self.get_array(size)
        for i in range(size):
            self.use(array_found + i)
        return array_found

# TODO: create new InfiniteList for storing type casting (chars, ints, bools, voids)

class Compiler:
    def __init__(self, mainnode) -> None:
        self.mainnode = mainnode
    
    def compile(self) -> str:
        self.aliases = {}
        self.literals = {}
        self.memory = MemoryUsageList()
        self.pointer = 0
        return self.visit(self.mainnode)
    
    def visit(self, node) -> None:
        result = ''
        
        if type(node) == DoNode:
            for child in node.body:
                result += self.visit(child)
            return result
        
        if type(node) == ConditionalNode:
            if node.token.full == (Tk.KW, 'while'):
                temp0, temp1 = self.memory.allocate(2)
                
                result += self.bf_parse('x[b0x]r_b0',
                    t0 = temp0,
                    x  = [BinaryOpNode(AddressNode(temp1), Token(Tk.OP, '='), node.condition)],
                    b0 = node.body,
                )
                
                self.memory.rmv(temp0, temp1)
                return result
            
            if node.token.full in [(Tk.KW, 'if'), (Tk.KW, 'elif')]:
                temp0, temp1, temp2, returned = self.memory.allocate(4)
                
                result += self.visit(node.condition)
                condition = self.pointer
                
                result += self.bf_parse('t0[-]+t1[-]x[b0t2[-]rv[-]r_b0[rv+t2+r_b0-]t2[r_b0+t2-]t0-x[t1+x-]]t1[x+t1-]t0[b1t2[-]rv[-]r_b1[rv+t2+r_b1-]t2[r_b1+t2-]t0-]rv',
                    #                                   \=====================================/                          \=====================================/
                    #                                       Set return value to if's return                                 Set return value to else's return
                    t0 = temp0,
                    t1 = temp1,
                    t2 = temp2,
                    x  = condition,
                    b0 = node.body,
                    b1 = node.elsebody,
                    rv = returned,
                )
                
                self.memory.rmv(temp0, temp1, temp2)
                return result
        
        if type(node) == BinaryOpNode:
            if node.token.full == (Tk.OP, '='):
                temp0 = self.memory.allocate()
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]x[-]y[x+t0+y-]t0[y+t0-]x',
                    t0 = temp0,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0)
                return result
                    
            if node.token.full == (Tk.OP, '+='):
                temp0 = self.memory.allocate()
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]y[x+t0+y-]t0[y+t0-]x',
                    t0 = temp0,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0)
                return result
                    
            if node.token.full == (Tk.OP, '-='):
                temp0 = self.memory.allocate()
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]y[x-t0+y-]t0[y+t0-]x',
                    t0 = temp0,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0)
                return result
            
            if node.token.full == (Tk.OP, '*='):
                temp0, temp1 = self.memory.allocate(2)
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]t1[-]x[t1+x-]t1[y[x+t0+y-]t0[y+t0-]t1-]x',
                    t0 = temp0,
                    t1 = temp1,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0, temp1)
                return result
            
            if node.token.full == (Tk.OP, '/='):
                temp0, temp1, temp2, temp3 = self.memory.allocate(4)
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]t1[-]t2[-]t3[-]x[t0+x-]t0[y[t1+t2+y-]t2[y+t2-]t1[t2+t0-[t2[-]t3+t0-]t3[t0+t3-]t2[t1-[x-t1[-]]+t2-]t1-]x+t0]x',
                    t0 = temp0,
                    t1 = temp1,
                    t2 = temp2,
                    t3 = temp3,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0, temp1, temp2, temp3)
                return result

            if node.token.full == (Tk.OP, '->'):
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('y[-]x[y+x-]y',
                    x = left,
                    y = right,
                )
                
                return result
            
            if node.token.full == (Tk.OP, '<->'):
                temp0 = self.memory.allocate()
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]x[t0+x-]y[x+y-]t0[y+t0-]x',
                    t0 = temp0,
                    x = left,
                    y = right,
                )
                
                self.memory.rmv(temp0)
                return result
            
            if node.token.full == (Tk.OP, '+'):
                temp0, returned = self.memory.allocate(2)
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]r[-]x[r+t0+x-]t0[x+t0-]t0[-]y[r+t0+y-]t0[y+t0-]r',
                    t0 = temp0,
                    r  = returned,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0)
                return result
            
            if node.token.full == (Tk.OP, '-'):
                temp0, returned = self.memory.allocate(2)
                
                result = self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]r[-]x[r+t0+x-]t0[x+t0-]t0[-]y[r-t0+y-]t0[y+t0-]r',
                    t0 = temp0,
                    r  = returned,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0)
                return result
            
            if node.token.full == (Tk.OP, '*'):
                temp0, temp1, returned = self.memory.allocate(3)
                
                result = self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]r[-]x[r+t0+x-]t0[x+t0-]t0[-]t1[-]r[t1+r-]t1[y[r+t0+y-]t0[y+t0-]t1-]r',
                    t0 = temp0,
                    t1 = temp1,
                    r  = returned,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0, temp1)
                return result
            
            if node.token.full == (Tk.OP, '/'):
                temp0, temp1, temp2, temp3, returned = self.memory.allocate(5)
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]r[-]x[r+t0+x-]t0[x+t0-]t0[-]t1[-]t2[-]t3[-]r[t0+r-]t0[y[t1+t2+y-]t2[y+t2-]t1[t2+t0-[t2[-]t3+t0-]t3[t0+t3-]t2[t1-[r-t1[-]]+t2-]t1-]r+t0]r',
                    t0 = temp0,
                    t1 = temp1,
                    t2 = temp2,
                    t3 = temp3,
                    r = returned,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0, temp1, temp2, temp3)
                return result
            
            # TODO: implement modulus
            
            if node.token.full == (Tk.OP, '=='):
                temp0, temp1, returned = self.memory.allocate(3)
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]r[-]x[r+t0+x-]t0[x+t0-]t1[-]r[t1+r-]+y[t1-t0+y-]t0[y+t0-]t1[r-t1[-]]r',
                    t0 = temp0,
                    t1 = temp1,
                    r  = returned,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0, temp1)
                return result
            
            if node.token.full == (Tk.OP, '!='):
                temp0, temp1, returned = self.memory.allocate(3)
                
                result += self.visit(node.left)
                left = self.pointer
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]r[-]x[r+t0+x-]t0[x+t0-]t1[-]r[t1+r-]y[t1-t0+y-]t0[y+t0-]t1[r+t1[-]]r',
                    t0 = temp0,
                    t1 = temp1,
                    r  = returned,
                    x  = left,
                    y  = right,
                )
                
                self.memory.rmv(temp0, temp1)
                return result
            
            # TODO: implement more comparison operators
                
            if node.token.full == (Tk.OP, ':'):
                if type(node.left) == IdentifierNode:
                    try:
                        self.aliases[node.left.title] = node.right.address
                    except AttributeError:
                        self.aliases[node.left.title] = node.right.right.address
                    return self.visit(node.right)
                        
            raise RuntimeError('binary operator not defined in compiler')
        
        if type(node) == UnaryOpNode:
            if node.token.full == (Tk.KW, 'print'):
                # FIXME: weird formatting, needs extensive testing
                if type(node.right) == ArrayNode:
                    result += self.visit(node.right)
                    for _ in range(len(node.right.array) + 1):
                        result += self.output()
                        result += self.right(1)
                    return result
                return self.visit(node.right) + self.output()
            
            if node.token.full == (Tk.KW, 'input'):
                return self.visit(node.right) + self.input()
            
            if node.token.full == (Tk.KW, 'not'):
                temp0, returned = self.memory.allocate(2)
                
                result += self.visit(node.right)
                right = self.pointer
                
                result += self.bf_parse('t0[-]r[-]x[r+t0+x-]t0[x+t0-]r-[t0-r-]t0[r+t0-]r',
                    t0 = temp0,
                    r  = returned,
                    x  = right,
                )
                
                self.memory.rmv(temp0)
                return result
            
            raise RuntimeError('unary operator not defined in compiler')
        
        if type(node) == AddressNode:
            return self.move(node.address)
        
        if type(node) == IdentifierNode:
            if node.title in self.aliases:
                return self.move(self.aliases[node.title])
            cell_found = self.memory.allocate()
            self.aliases[node.title] = cell_found
            return self.move(self.aliases[node.title])
        
        if type(node) == LiteralNode:
            cell_found = self.memory.allocate()
            return self.move(cell_found) + self.assign(node.value)
        
        if type(node) == ArrayNode:
            array_address = self.memory.allocate_array(len(node.array))
            for i, subnode in enumerate(node.array):
                if type(subnode) == LiteralNode:
                    result += self.move(array_address + i)
                    result += self.assign(subnode.value)
                    continue
                result += self.visit(BinaryOpNode(AddressNode(array_address + i), Token(Tk.OP, '='), subnode))
            result += self.move(array_address)
            return result
    
    def bf_parse(self, bf: str, **mapping: Union[Callable, List[Callable]]):
        def repl(id_str):
            if type(mapping[id_str]) == int:
                return self.move(mapping[id_str])
            total = ''
            returned = 0
            for child in mapping[id_str]:
                total += self.visit(child)
                returned = self.pointer
            mapping['r_'+id_str] = returned
            return total

        i = 0
        while i < len(bf):
            character = bf[i]
            if character in LETTERS + DIGITS + '_':
                id_str = ''
                while id_str not in mapping.keys() and i < len(bf):
                    character = bf[i]
                    id_str += character
                    i += 1
                repl_str = repl(id_str)
                bf = bf.replace(id_str, repl_str, 1)
                i += len(repl_str) - len(id_str)
            else:
                i += 1
        return bf
                
    # Instructions
    
    def move(self, address_target: int) -> str:
        pointer = self.pointer
        self.pointer = address_target
        
        if address_target > pointer:
            return '>' * (address_target - pointer)
        return '<' * (pointer - address_target)
    
    def assign(self, value_target: int) -> str:
        return '[-]' + '+' * value_target

    def right(self, address_increment: int) -> str:
        self.pointer += address_increment if address_increment != None else 1
        return '>' * address_increment

    def left(self, address_decrement: int) -> str:
        self.pointer -= address_decrement if address_decrement != None else 1
        return '<' * address_decrement

    def add(self, value_increment: int) -> str:
        return '+' * value_increment if value_increment != None else 1

    def sub(self, value_decrement: int) -> str:
        return '-' * value_decrement if value_decrement != None else 1

    def output(self, output_address: int = None) -> str:
        return self.move_append(output_address, '.')

    def input(self, input_address: int = None) -> str:
        return self.move_append(input_address, ',')

    def move_append(self, address: int, symbol: str) -> str:
        if address != None:
            pointer = self.pointer
            self.pointer = address
        
            if address > pointer:
                return '>' * (address - pointer) + symbol
            if address < pointer:
                return '<' * (pointer - address) + symbol
        return symbol

def ComplexEncoder(object: Node) -> Union[dict, str]:
    if hasattr(object, 'reprJSON'):
        return object.reprJSON()
    else:
        return repr(object)

def run(filename: str, filetext: str, debug: bool = False):
    lexer = Lexer(filename, filetext)
    tokens, error = lexer.lex()
    
    if error: return None, error
    
    if debug:
        with open('debug/tokens.txt', 'w') as tokens_txt:
            tokens_txt.write('\n'.join(repr(token) for token in tokens))
        
    parser = Parser(filename, tokens)
    parsetree, error = parser.parse()
    
    if error: return None, error
    
    if debug:
        with open('debug/parsetree.json', 'w') as parsetree_json:
            json.dump(parsetree, parsetree_json, default=ComplexEncoder, indent=4)

    compiler = Compiler(parsetree)
    bf = compiler.compile()
    
    if debug:
        with open('debug/compiled.bf', 'w') as compiled_bf:
            compiled_bf.write('\n'.join(bf[i:i+64] for i in range(0, len(bf), 64)))

    return bf, None

def main():
    if len(sys.argv) > 1: file_name = sys.argv[1]
    else: file_name = 'debug/main.ms'
    
    with open(file_name, 'r') as file:
        bf, error = run(file_name, file.read(), debug = True)
    if error:
        print(error)
    else:
        import brainfuck
        brainfuck.evaluate(bf)
        
if __name__ == '__main__': main()
